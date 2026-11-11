"""Launch flows use real HTTP authorization and disposable databases; never production data."""
from datetime import UTC, datetime, timedelta
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.security import access_token
from app.modules.auth.models import User
from app.modules.cms.models import MediaAsset
from app.modules.cms.services import CMSService
from app.modules.coaching.models import Exercise, Program, ProgramAssignment
from app.modules.commerce.models import EntitlementGrant, Order, Product, Subscription
from app.modules.experience.models import Notification
from app.modules.leads.models import Lead


@pytest.fixture
def launch(db, monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), 'storage_provider', 'local')
    monkeypatch.setattr(get_settings(), 'media_root', tmp_path)
    monkeypatch.setattr(get_settings(), 'live_payments_enabled', False)
    users = {}
    for name, role in [('admin', 'ADMIN'), ('coach', 'COACH'), ('member', 'CLIENT'), ('other', 'CLIENT')]:
        users[name] = User(name=name, email=f'{name}@launch.example.com', role=role, password_hash='unused', active=True)
        db.add(users[name])
    db.flush()
    exercises = [Exercise(name=f'Exercise {i}', muscle_group='Legs', owner_id=users['coach'].id, published=True) for i in range(2)]
    db.add_all(exercises)
    db.flush()
    asset = MediaAsset(owner_id=users['coach'].id, storage_key='private.mp4', content_type='video/mp4', size=24, purpose='exercise', public=True)
    db.add(asset)
    db.flush()
    exercises[0].video_media_id = asset.id
    (tmp_path / 'private.mp4').write_bytes(b'0123456789private workout')
    program = Program(owner_id=users['coach'].id, name='Foundation', published=True, workouts=[{'id': 'day-1', 'name': 'Strength', 'day': 1, 'exercises': [{'exercise_id': exercises[0].id, 'name': 'Squat', 'sets': 3, 'reps': '10'}]}])
    db.add(program)
    db.commit()
    headers = {name: {'Authorization': f'Bearer {access_token(user)}'} for name, user in users.items()}
    return users, headers, program, exercises, asset


def grant(client, launch, *, key='program_access', resource=None, user='member', expires=None):
    users, headers, program, _, _ = launch
    return client.post('/api/v1/launch/admin/access', headers=headers['admin'], json={
        'user_id': users[user].id, 'key': key, 'resource_id': program.id if resource is None else resource,
        'reason': 'Approved coaching pilot', 'source_type': 'PILOT',
        'expires_at': (expires or datetime.now(UTC) + timedelta(days=30)).isoformat()})


def test_public_programs_are_only_descriptions_and_library_is_private(client, db, launch):
    _, headers, program, exercises, asset = launch
    for path in ['/api/v1/programs', '/api/v1/launch/programs']:
        response = client.get(path)
        assert response.status_code == 200
        assert 'workouts' not in response.json()['items'][0]
        assert exercises[0].id not in response.text and asset.id not in response.text
    assert client.get(f'/api/v1/launch/programs/{program.id}').status_code == 200
    assert client.get('/api/v1/exercises').status_code == 401
    assert client.get('/api/v1/exercises', headers=headers['member']).status_code == 403
    for method in ['get', 'head']:
        assert getattr(client, method)(f'/api/v1/media/{asset.id}/file', headers={'Range': 'bytes=0-5'}).status_code == 401
        assert getattr(client, method)(f'/api/v1/media/{asset.id}/file', headers=headers['member']).status_code == 403


def test_program_access_is_scoped_revocable_and_rechecked_for_existing_media_tokens(client, db, launch):
    users, headers, program, exercises, asset = launch
    result = grant(client, launch)
    assert result.status_code == 201, result.text
    assignment = db.scalar(select(ProgramAssignment).where(ProgramAssignment.client_id == users['member'].id))
    assert assignment.snapshot['workouts'][0]['exercises'][0]['exercise_id'] == exercises[0].id
    authorized = client.get('/api/v1/exercises', headers=headers['member']).json()['items']
    assert [row['id'] for row in authorized] == [exercises[0].id]
    token_url = authorized[0]['video_url']
    assert '?token=' in token_url
    assert client.get(token_url, headers={'Range': 'bytes=0-5'}).status_code == 206
    assert client.get(f'/api/v1/media/{asset.id}/file', headers=headers['other']).status_code == 403
    assert client.patch(f'/api/v1/media/{asset.id}', headers=headers['member'], json={'caption': 'tampered'}).status_code in (403, 404)
    assert client.delete(f'/api/v1/media/{asset.id}', headers=headers['member']).status_code in (403, 404)
    assert client.delete(f"/api/v1/launch/admin/access/{result.json()['id']}", headers=headers['admin']).status_code == 200
    assert client.get(token_url).status_code == 403
    assert client.get('/api/v1/exercises', headers=headers['member']).status_code == 403
    expired = client.get('/api/v1/programs/assignments', headers=headers['member']).json()['items'][0]
    assert expired['snapshot']['workouts'] == []
    assert expired['status'] == 'ACCESS_ENDED'
    response = client.post('/api/v1/workouts/sessions', headers=headers['member'], json={'assignment_id': assignment.id, 'workout_id': 'day-1', 'sets': [], 'completed': True})
    assert response.status_code == 403
    assert db.scalar(select(func.count()).select_from(Subscription)) == 0
    assert db.scalar(select(func.count()).select_from(Order)) == 0


def test_expiry_and_future_grants_do_not_give_access(client, db, launch):
    _, headers, _, _, _ = launch
    result = grant(client, launch)
    record = db.get(EntitlementGrant, result.json()['id'])
    record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert client.get('/api/v1/exercises', headers=headers['member']).status_code == 403
    record.expires_at = datetime.now(UTC) + timedelta(days=10)
    record.starts_at = datetime.now(UTC) + timedelta(days=1)
    db.commit()
    assert client.get('/api/v1/exercises', headers=headers['member']).status_code == 403
    assert client.get('/api/v1/launch/access/mine', headers=headers['member']).json()['items'] == []
    assert grant(client, launch, expires=datetime.now(UTC) - timedelta(days=1)).status_code == 422


def test_legacy_explicit_assignments_and_membership_grants_continue_to_work(client, db, launch):
    users, headers, program, exercises, _ = launch
    assignment = ProgramAssignment(client_id=users['member'].id, program_id=program.id, assigned_by=users['admin'].id, snapshot={'workouts': program.workouts}, status='ACTIVE')
    db.add(assignment)
    db.commit()
    assert len(client.get('/api/v1/exercises', headers=headers['member']).json()['items']) == 1
    result = grant(client, launch, key='exercise_library', resource='')
    assert result.status_code == 201
    assert len(client.get('/api/v1/exercises', headers=headers['member']).json()['items']) == len(exercises)
    assert client.get('/api/v1/entitlements', headers=headers['member']).json()['entitlements']['exercise_library'] is True


def test_only_administrators_can_manage_launch_access_and_flags(client, launch):
    users, headers, program, _, _ = launch
    body = {'user_id': users['member'].id, 'key': 'program_access', 'resource_id': program.id, 'reason': 'Test access', 'expires_at': (datetime.now(UTC) + timedelta(days=1)).isoformat()}
    for role in ['member', 'other', 'coach']:
        assert client.post('/api/v1/launch/admin/access', json=body, headers=headers[role]).status_code == 403
        assert client.get('/api/v1/launch/admin/access', headers=headers[role]).status_code == 403
        assert client.patch('/api/v1/launch/config', json={'enrollment': False}, headers=headers[role]).status_code == 403
        assert client.put(f'/api/v1/launch/programs/{program.id}/introduction', json={}, headers=headers[role]).status_code == 403


def test_enrollment_notifies_admin_without_orders_or_access_and_history_is_owned(client, db, launch):
    users, headers, program, _, _ = launch
    body = {'name': 'New member', 'email': users['member'].email, 'goal': 'Build strength', 'experience': 'Beginner', 'environment': 'Home', 'training_days': [1, 3], 'obstacle': 'Time', 'program_id': program.id, 'consent': True, 'consent_version': CMSService(db).settings()['legal_version']}
    guest = client.post('/api/v1/launch/enrollments', json=body)
    assert guest.status_code == 201, guest.text
    assert db.get(Lead, guest.json()['id']).user_id is None
    assert client.get('/api/v1/launch/enrollments/mine', headers=headers['member']).json()['items'] == []
    signed = client.post('/api/v1/launch/enrollments', json=body, headers=headers['member'])
    assert signed.status_code == 201, signed.text
    lead = db.get(Lead, signed.json()['id'])
    assert lead.user_id == users['member'].id and lead.responses['obstacle'] == 'Time'
    history = client.get('/api/v1/launch/enrollments/mine', headers=headers['member']).json()['items']
    assert [item['id'] for item in history] == [lead.id]
    assert 'notes' not in history[0] and 'responses' not in history[0]
    assert client.get('/api/v1/launch/enrollments/mine', headers=headers['other']).json()['items'] == []
    assert db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == users['admin'].id)) == 2
    for model in [Order, Subscription, EntitlementGrant, ProgramAssignment]:
        assert db.scalar(select(func.count()).select_from(model)) == 0
    assert client.post('/api/v1/launch/enrollments', json={**body, 'consent': False}).status_code == 422
    assert client.post('/api/v1/launch/enrollments', json={**body, 'consent_version': 'outdated'}).status_code == 409
    assert client.post('/api/v1/launch/enrollments', json={**body, 'training_days': [1, 1]}).status_code == 422


def test_catalog_prices_preview_and_private_delivery(client, db, launch, tmp_path):
    users, headers, program, _, _ = launch
    private = MediaAsset(owner_id=users['admin'].id, storage_key='full.pdf', content_type='application/pdf', size=16, purpose='digital', public=False)
    preview = MediaAsset(owner_id=users['admin'].id, storage_key='preview.pdf', content_type='application/pdf', size=9, purpose='promotion', public=True)
    db.add_all([private, preview])
    db.commit()
    (tmp_path / 'full.pdf').write_bytes(b'%PDF full secret')
    (tmp_path / 'preview.pdf').write_bytes(b'%PDF free')
    body = {'name': 'Home guide', 'type': 'DIGITAL', 'status': 'PUBLISHED', 'categories': ['Home'], 'prices': [{'currency': 'RWF', 'amount_minor': 20000}, {'currency': 'USD', 'amount_minor': 1800}], 'preview_media_id': preview.id, 'paid_media_ids': [private.id], 'program_ids': [program.id]}
    created = client.post('/api/v1/launch/admin/catalog', headers=headers['admin'], json=body)
    assert created.status_code == 201, created.text
    product_id = created.json()['id']
    assert created.json()['paid_media_ids'] == [private.id]
    for path in ['/api/v1/launch/catalog?kind=DIGITAL', f'/api/v1/launch/catalog/{product_id}', '/api/v1/products']:
        response = client.get(path)
        assert response.status_code == 200, response.text
        assert private.id not in response.text and 'paid_media_ids' not in response.text and 'full.pdf' not in response.text
    assert client.get(f'/api/v1/media/{preview.id}/file').status_code == 200
    assert client.get(f'/api/v1/media/{private.id}/file').status_code == 401
    assert client.get(f'/api/v1/launch/catalog/{product_id}/resources', headers=headers['member']).status_code == 403
    assert grant(client, launch, key='digital_product', resource=product_id).status_code == 201
    response = client.get(f'/api/v1/launch/catalog/{product_id}/resources', headers=headers['member'])
    assert response.status_code == 200
    url = response.json()['items'][0]['url']
    assert client.get(url).content == b'%PDF full secret'
    assert client.get(f'/api/v1/media/{private.id}/file', headers=headers['other']).status_code == 403
    # Defense in depth: even a legacy or mistakenly public flag cannot expose a linked paid file.
    private.public, private.purpose = True, 'promotion'
    db.commit()
    assert client.get(f'/api/v1/media/{private.id}/file').status_code == 401
    assert client.post('/api/v1/launch/admin/catalog', headers=headers['admin'], json={**body, 'paid_media_ids': [preview.id]}).status_code == 422
    assert client.put(f'/api/v1/launch/admin/catalog/{product_id}', headers=headers['admin'], json={**body, 'paid_media_ids': [], 'prices': []}).status_code == 200
    assert client.get(url).status_code == 403
    assert client.get(f'/api/v1/launch/catalog/{product_id}').json()['prices'] == []


def test_private_files_cannot_be_promotional_and_uploads_validate_content(client, db, launch):
    _, headers, program, _, asset = launch
    assert client.put(f'/api/v1/launch/programs/{program.id}/introduction', headers=headers['admin'], json={'intro_media_id': asset.id}).status_code == 422
    content = BytesIO()
    Image.new('RGB', (4, 4)).save(content, format='PNG')
    path = '/api/v1/launch/admin/assets'
    for role in ['member', 'coach']:
        assert client.post(path, headers=headers[role], data={'purpose': 'cover', 'caption': 'Test', 'publish': 'true'}, files={'file': ('image.png', content.getvalue(), 'image/png')}).status_code == 403
    assert client.post(path, headers=headers['admin'], data={'purpose': 'cover', 'caption': 'Test'}, files={'file': ('image.png', content.getvalue(), 'image/png')}).status_code == 422
    created = client.post(path, headers=headers['admin'], data={'purpose': 'cover', 'caption': 'Test', 'publish': 'true'}, files={'file': ('image.png', content.getvalue(), 'image/png')})
    assert created.status_code == 201, created.text
    assert created.json()['public'] is True
    assert client.get(created.json()['url']).status_code == 200
    assert client.post(path, headers=headers['admin'], data={'purpose': 'cover', 'caption': 'Test', 'publish': 'true'}, files={'file': ('bad.png', b'<script>', 'image/png')}).status_code == 422


def test_flags_disable_public_flows_and_payment_credentials_cannot_enable_checkout(client, db, launch, monkeypatch):
    _, headers, _, _, _ = launch
    product = Product(name='Hidden digital', type='DIGITAL', status='PUBLISHED', active=True, price_minor=10, currency='USD')
    db.add(product)
    db.commit()
    response = client.patch('/api/v1/launch/config', headers=headers['admin'], json={'digital_store': False, 'program_discovery': False, 'enrollment': False})
    assert response.status_code == 200 and response.json()['live_payments'] is False
    assert client.get('/api/v1/launch/programs').status_code == 404
    assert client.get('/api/v1/launch/catalog?kind=DIGITAL').status_code == 404
    assert client.get('/api/v1/launch/catalog').json()['items'] == []
    monkeypatch.setattr(get_settings(), 'flutterwave_secret_key', 'configured-but-disabled')
    monkeypatch.setattr(get_settings(), 'flutterwave_webhook_secret', 'configured-but-disabled')
    assert client.get('/api/v1/payments/status').json()['available'] is False
    assert client.post('/api/v1/payments/verify', headers=headers['member'], json={'order_id': 'fake', 'transaction_id': '123'}).status_code == 503
    assert client.post('/api/v1/payments/webhook', json={}).status_code == 503


def test_legacy_product_editor_updates_only_its_configured_currency(client, launch):
    _, headers, _, _, _ = launch
    created = client.post('/api/v1/launch/admin/catalog', headers=headers['admin'], json={
        'name': 'Independent prices', 'status': 'PUBLISHED', 'prices': [
            {'currency': 'RWF', 'amount_minor': 50000, 'pricing_type': 'monthly'},
            {'currency': 'USD', 'amount_minor': 4500, 'pricing_type': 'monthly'}]})
    assert created.status_code == 201
    product_id = created.json()['id']
    patched = client.patch(f'/api/v1/products/{product_id}', headers=headers['admin'], json={'price_minor': 60000})
    assert patched.status_code == 200
    prices = client.get(f'/api/v1/launch/catalog/{product_id}').json()['prices']
    assert {p['currency']: p['amount_minor'] for p in prices} == {'RWF': 60000, 'USD': 4500}
