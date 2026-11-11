import copy
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.permissions import require_admin
from app.core.repository import audit, persist, require_record, serialize
from app.core.security import utc
from app.modules.auth.models import User
from app.modules.cms.models import MediaAsset, Setting
from app.modules.coaching.models import Program, ProgramAssignment
from app.modules.commerce.models import DigitalAsset, EntitlementGrant, Product, ProductPrice
from app.modules.launch.schemas import CatalogInput, GrantInput, LaunchFlags, ProgramIntroduction


def flags(db: Session) -> dict:
    record = db.scalar(select(Setting).where(Setting.key == 'launch_flags'))
    return {**LaunchFlags().model_dump(), **(record.value if record else {}), 'live_payments': False}


def enabled(db: Session, key: str):
    if not flags(db)[key]:
        raise AppError(404, 'FEATURE_UNAVAILABLE', 'This experience is not available yet')


def public_asset(db: Session, asset_id: str | None, *, video: bool = False) -> str | None:
    if not asset_id:
        return None
    asset = db.get(MediaAsset, asset_id)
    if not asset or not asset.public or asset.purpose not in {'marketing', 'promotion'}:
        return None
    if video and not asset.content_type.startswith('video/'):
        return None
    return f'/api/v1/media/{asset.id}/file'


def validate_promotion(db: Session, asset_id: str | None, *, video: bool = False):
    if asset_id and not public_asset(db, asset_id, video=video):
        raise AppError(422, 'PROMOTIONAL_MEDIA_REQUIRED', 'Select an explicitly public promotional asset, not a private training file')


def program_output(db: Session, program: Program) -> dict:
    details = ProgramIntroduction.model_validate(program.launch_details or {}).model_dump(mode='json')
    if 'days_per_week' not in (program.launch_details or {}):
        details['days_per_week'] = len({workout.get('day') for workout in program.workouts if workout.get('day')}) or None
    if 'minutes_per_session' not in (program.launch_details or {}):
        details['minutes_per_session'] = None
    return {**{key: getattr(program, key) for key in ('id', 'name', 'description', 'goal', 'difficulty', 'weeks')},
            **details, 'cover_url': public_asset(db, details['cover_media_id']),
            'intro_url': public_asset(db, details['intro_media_id'], video=True),
            'demonstration_urls': [url for item in details['demonstration_media_ids'] if (url := public_asset(db, item, video=True))]}


def product_output(db: Session, product: Product, admin: bool = False) -> dict:
    prices = db.scalars(select(ProductPrice).where(ProductPrice.product_id == product.id, ProductPrice.active.is_(True))).all()
    amounts = [{'currency': item.currency, 'amount_minor': item.amount_minor, 'pricing_type': item.pricing_type} for item in prices]
    if not amounts and product.price_minor > 0:
        amounts = [{'currency': product.currency, 'amount_minor': product.price_minor, 'pricing_type': product.billing_interval}]
    details = product.launch_details or {}
    data = {key: getattr(product, key) for key in ('id', 'name', 'description', 'full_description', 'type', 'categories', 'features', 'featured', 'faq', 'status', 'active')}
    data.update({key: details.get(key, [] if key == 'program_ids' else '') for key in ('program_ids', 'support_level', 'duration', 'renewal', 'cancellation', 'suitability', 'delivery')})
    data.update(prices=amounts, availability=details.get('availability', 'COMING_SOON'), cover_url=public_asset(db, product.cover_media_id), preview_url=public_asset(db, details.get('preview_media_id')))
    if admin:
        data.update(cover_media_id=product.cover_media_id, preview_media_id=details.get('preview_media_id'),
                    paid_media_ids=list(db.scalars(select(DigitalAsset.media_id).where(DigitalAsset.product_id == product.id, DigitalAsset.active.is_(True))).all()))
    return data


def save_catalog(db: Session, data: CatalogInput, user: User, product_id: str | None = None) -> dict:
    require_admin(user)
    validate_promotion(db, data.cover_media_id)
    validate_promotion(db, data.preview_media_id)
    for program_id in data.program_ids:
        require_record(db, Program, program_id)
    for media_id in data.paid_media_ids:
        asset = require_record(db, MediaAsset, media_id)
        if asset.public or asset.purpose != 'digital':
            raise AppError(422, 'PRIVATE_ASSET_REQUIRED', 'Paid files must use private digital-product uploads')
        existing = db.scalar(select(DigitalAsset).where(DigitalAsset.media_id == media_id))
        if existing and existing.product_id != product_id:
            raise AppError(409, 'ASSET_IN_USE', 'This file already belongs to another product')
    product = require_record(db, Product, product_id) if product_id else Product(name=data.name, price_minor=0, currency='RWF', billing_interval='one_time')
    for key in ('name', 'description', 'full_description', 'type', 'status', 'active', 'featured', 'categories', 'features', 'cover_media_id'):
        setattr(product, key, getattr(data, key))
    product.faq = [faq.model_dump() for faq in data.faq]
    product.launch_details = data.model_dump(mode='json', include={'program_ids', 'preview_media_id', 'support_level', 'duration', 'renewal', 'cancellation', 'suitability', 'delivery', 'availability'})
    if data.prices:
        price = data.prices[0]
        product.price_minor, product.currency, product.billing_interval = price.amount_minor, price.currency, price.pricing_type
    else:
        product.price_minor = 0
    db.add(product)
    db.flush()
    for old in db.scalars(select(ProductPrice).where(ProductPrice.product_id == product.id)):
        old.active = False
    for price in data.prices:
        row = db.scalar(select(ProductPrice).where(ProductPrice.product_id == product.id, ProductPrice.currency == price.currency, ProductPrice.pricing_type == price.pricing_type, ProductPrice.country_code == ''))
        if not row:
            row = ProductPrice(product_id=product.id, **price.model_dump())
        row.amount_minor, row.active = price.amount_minor, True
        db.add(row)
    for old_asset in db.scalars(select(DigitalAsset).where(DigitalAsset.product_id == product.id)):
        old_asset.active = old_asset.media_id in data.paid_media_ids
    for index, media_id in enumerate(data.paid_media_ids):
        resource = db.scalar(select(DigitalAsset).where(DigitalAsset.media_id == media_id))
        if not resource:
            resource = DigitalAsset(product_id=product.id, media_id=media_id, label='Private digital resource', asset_type='FILE', sort_order=index)
        resource.active = True
        db.add(resource)
    persist(db, product, user.id, 'catalog.saved')
    return product_output(db, product, admin=True)


def grant_access(db: Session, data: GrantInput, user: User) -> dict:
    require_admin(user)
    client = require_record(db, User, data.user_id)
    if client.role != 'CLIENT' or not client.active:
        raise AppError(422, 'INVALID_CLIENT', 'Select an active client')
    if utc(data.expires_at) <= datetime.now(UTC):
        raise AppError(422, 'INVALID_EXPIRY', 'Access must expire in the future')
    if data.key == 'exercise_library' and data.resource_id:
        raise AppError(422, 'INVALID_SCOPE', 'Library membership does not use a resource ID')
    source_id = str(uuid4())
    if data.key == 'program_access':
        program = require_record(db, Program, data.resource_id)
        assignment = ProgramAssignment(client_id=client.id, program_id=program.id, assigned_by=user.id, snapshot=copy.deepcopy(serialize(program)), status='ACTIVE')
        # JSON snapshots exclude database timestamps and preserve the assigned plan.
        assignment.snapshot = {key: value for key, value in assignment.snapshot.items() if key not in {'created_at', 'updated_at'}}
        db.add(assignment)
        db.flush()
        source_id = assignment.id
    elif data.key == 'digital_product':
        product = require_record(db, Product, data.resource_id)
        if product.type != 'DIGITAL':
            raise AppError(422, 'INVALID_RESOURCE', 'Choose a digital product for resource access')
    grant = EntitlementGrant(**data.model_dump(), granted_by=user.id, source_id=source_id, starts_at=datetime.now(UTC))
    return persist(db, grant, user.id, 'access.granted')


def revoke_access(db: Session, grant_id: str, user: User):
    require_admin(user)
    grant = require_record(db, EntitlementGrant, grant_id)
    grant.revoked_at = datetime.now(UTC)
    if grant.key == 'program_access':
        assignment = db.get(ProgramAssignment, grant.source_id)
        if assignment and assignment.client_id == grant.user_id:
            assignment.status = 'REVOKED'
    audit(db, user.id, 'access.revoked', grant)
    db.commit()
    return serialize(grant)
