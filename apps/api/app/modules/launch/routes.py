import asyncio
import secrets
from typing import Literal

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.core.exceptions import AppError
from app.core.permissions import DB, Identity, OptionalIdentity, require_admin
from app.core.repository import paginate, persist, require_record
from app.modules.cms.models import MediaAsset, Setting
from app.modules.cms.services import CMSService, read_validated_upload
from app.modules.coaching.models import Program
from app.modules.coaching.video import validate_video
from app.modules.commerce.entitlements import EntitlementService
from app.modules.commerce.models import DigitalAsset, EntitlementGrant, Product
from app.modules.launch.schemas import (
    CatalogInput,
    EnrollmentInput,
    GrantInput,
    LaunchFlags,
    ProgramIntroduction,
)
from app.modules.launch.services import (
    enabled,
    flags,
    grant_access,
    product_output,
    program_output,
    revoke_access,
    save_catalog,
    validate_promotion,
)
from app.modules.leads.models import Lead
from app.modules.leads.schemas import LeadCreate
from app.modules.leads.services import LeadService
from app.providers.storage import storage_provider

router = APIRouter(prefix='/launch', tags=['Discovery and enrollment'])


@router.get('/config')
def config(db: DB):
    return flags(db)


@router.patch('/config')
def update_config(data: LaunchFlags, db: DB, user: Identity):
    require_admin(user)
    record = db.scalar(select(Setting).where(Setting.key == 'launch_flags')) or Setting(key='launch_flags')
    record.value = data.model_dump()
    persist(db, record, user.id, 'launch.flags_updated')
    return flags(db)


@router.get('/programs')
def programs(db: DB, limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0)):
    enabled(db, 'program_discovery')
    page = paginate(db, select(Program).where(Program.published.is_(True)).order_by(Program.created_at.desc()), limit, offset)
    page['items'] = [program_output(db, require_record(db, Program, row['id'])) for row in page['items']]
    return page


@router.get('/programs/{program_id}')
def introduction(program_id: str, db: DB):
    enabled(db, 'program_discovery')
    program = require_record(db, Program, program_id)
    if not program.published:
        raise AppError(404, 'PROGRAM_UNAVAILABLE', 'Program is not available')
    return program_output(db, program)


@router.put('/programs/{program_id}/introduction')
def save_introduction(program_id: str, data: ProgramIntroduction, db: DB, user: Identity):
    require_admin(user)
    program = require_record(db, Program, program_id)
    validate_promotion(db, data.cover_media_id)
    validate_promotion(db, data.intro_media_id, video=True)
    for media_id in data.demonstration_media_ids:
        validate_promotion(db, media_id, video=True)
    program.launch_details = data.model_dump(mode='json')
    persist(db, program, user.id, 'program.introduction_updated')
    return program_output(db, program)


@router.get('/catalog')
def catalog(db: DB, kind: Literal['DIGITAL', 'COACHING', 'MEMBERSHIP'] | None = None,
            program_id: str | None = None, q: str = '', category: str = '',
            limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    if kind == 'DIGITAL':
        enabled(db, 'digital_store')
    statement = select(Product).where(Product.active.is_(True), Product.status == 'PUBLISHED', Product.visibility == 'PUBLIC')
    if not flags(db)['digital_store']:
        statement = statement.where(Product.type != 'DIGITAL')
    if kind:
        statement = statement.where(Product.type == kind)
    if q:
        statement = statement.where(Product.name.ilike('%' + q[:120] + '%'))
    # JSON membership remains portable across local SQLite and Azure PostgreSQL.
    products = db.scalars(statement.order_by(Product.featured.desc(), Product.created_at.desc())).all()
    rows = [product for product in products if (not category or category in product.categories)
            and (not program_id or program_id in (product.launch_details or {}).get('program_ids', []))]
    return {'items': [product_output(db, product) for product in rows[offset:offset+limit]], 'total': len(rows)}


@router.get('/catalog/{product_id}')
def catalog_detail(product_id: str, db: DB):
    product = require_record(db, Product, product_id)
    if not product.active or product.status != 'PUBLISHED' or product.visibility != 'PUBLIC':
        raise AppError(404, 'PRODUCT_UNAVAILABLE', 'Product is not available')
    if product.type == 'DIGITAL':
        enabled(db, 'digital_store')
    return product_output(db, product)


@router.get('/admin/catalog')
def admin_catalog(db: DB, user: Identity, limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0)):
    require_admin(user)
    page = paginate(db, select(Product).order_by(Product.created_at.desc()), limit, offset)
    page['items'] = [product_output(db, require_record(db, Product, row['id']), admin=True) for row in page['items']]
    return page


@router.post('/admin/catalog', status_code=201)
def create_catalog(data: CatalogInput, db: DB, user: Identity):
    return save_catalog(db, data, user)


@router.put('/admin/catalog/{product_id}')
def update_catalog(product_id: str, data: CatalogInput, db: DB, user: Identity):
    return save_catalog(db, data, user, product_id)


@router.post('/enrollments', status_code=201)
def enrollment(data: EnrollmentInput, request: Request, db: DB, user: OptionalIdentity):
    enabled(db, 'enrollment')
    if data.consent_version != CMSService(db).settings()['legal_version']:
        raise AppError(409, 'CONSENT_CHANGED', 'Please review the current privacy information and submit again')
    if data.program_id:
        introduction(data.program_id, db)
    if data.product_id:
        product = catalog_detail(data.product_id, db)
        if data.program_id and data.program_id not in product['program_ids']:
            raise AppError(422, 'PACKAGE_MISMATCH', 'Choose a package offered for this program')
    responses = data.model_dump(mode='json', exclude={'name', 'email', 'phone', 'goal', 'consent', 'consent_version'})
    lead = LeadCreate(name=data.name.strip(), email=data.email, phone=data.phone, goal=data.goal,
                      source=data.kind, consent=True, consent_version=data.consent_version, responses=responses)
    return LeadService(db).create(lead, request, user_id=user.id if user else None)


@router.get('/enrollments/mine')
def my_enrollments(db: DB, user: Identity, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    page = paginate(db, select(Lead).where(Lead.user_id == user.id).order_by(Lead.created_at.desc()), limit, offset)
    page['items'] = [{key: row[key] for key in ('id', 'goal', 'stage', 'source', 'created_at')} for row in page['items']]
    return page


@router.get('/admin/access')
def list_access(db: DB, user: Identity, client_id: str | None = None, limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0)):
    require_admin(user)
    query = select(EntitlementGrant).order_by(EntitlementGrant.created_at.desc())
    if client_id:
        query = query.where(EntitlementGrant.user_id == client_id)
    return paginate(db, query, limit, offset)


@router.post('/admin/access', status_code=201)
def give_access(data: GrantInput, db: DB, user: Identity):
    return grant_access(db, data, user)


@router.delete('/admin/access/{grant_id}')
def remove_access(grant_id: str, db: DB, user: Identity):
    return revoke_access(db, grant_id, user)


@router.post('/admin/assets', status_code=201)
async def upload_asset(db: DB, user: Identity, file: UploadFile = File(),
                       purpose: Literal['cover', 'introduction', 'preview', 'digital'] = Form(),
                       caption: str = Form(max_length=300), publish: bool = Form(False)):
    require_admin(user)
    public = purpose != 'digital'
    if public and not publish:
        raise AppError(422, 'PUBLICATION_CONFIRMATION_REQUIRED', 'Confirm that you own this promotional content and want it public')
    if purpose == 'cover' and (file.content_type or '').startswith('video/'):
        raise AppError(422, 'IMAGE_REQUIRED', 'Choose an image for the cover')
    provider = storage_provider()
    if purpose == 'introduction' or (file.content_type or '').startswith('video/'):
        video = await validate_video(file)
        key = secrets.token_hex(24) + '.' + video.extension
        kind, size = video.content_type, video.size
        await asyncio.to_thread(provider.save_file, key, file.file, kind)
    else:
        content, kind, extension = await read_validated_upload(file)
        if purpose == 'cover' and not kind.startswith('image/'):
            raise AppError(422, 'IMAGE_REQUIRED', 'Choose an image for the cover')
        key, size = secrets.token_hex(24) + '.' + extension, len(content)
        await asyncio.to_thread(provider.save, key, content, kind)
    asset = MediaAsset(owner_id=user.id, storage_key=key, content_type=kind, size=size,
                       caption=caption, purpose='promotion' if public else 'digital', public=public)
    try:
        await run_in_threadpool(persist, db, asset, user.id, 'launch.asset_uploaded')
    except Exception:
        await asyncio.to_thread(provider.delete, key)
        raise
    return CMSService(db).media_output(asset, user)


@router.get('/access/mine')
def my_access(db: DB, user: Identity):
    from app.core.repository import serialize
    grants = EntitlementService(db).grants(user.id)
    return {'items': [{key: value for key, value in serialize(grant).items()
                       if key in {'id', 'key', 'resource_id', 'source_type', 'starts_at', 'expires_at'}} for grant in grants],
            'entitlements': EntitlementService(db).current(user.id)}


@router.get('/catalog/{product_id}/resources')
def resources(product_id: str, db: DB, user: Identity):
    if not EntitlementService(db).permits(user.id, 'digital_product', product_id):
        raise AppError(403, 'ENTITLEMENT_REQUIRED', 'This resource is not included in your access')
    assets = db.scalars(select(DigitalAsset).where(DigitalAsset.product_id == product_id, DigitalAsset.active.is_(True)).order_by(DigitalAsset.sort_order)).all()
    return {'items': [CMSService(db).media_output(asset, user) for link in assets
                      if (asset := db.get(MediaAsset, link.media_id)) and asset.purpose != 'archived']}
