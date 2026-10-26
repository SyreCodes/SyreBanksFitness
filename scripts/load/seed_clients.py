"""Create synthetic clients only in an explicitly named localhost load-test database."""
import argparse
import json
import os
import secrets
from pathlib import Path

from app.core import models  # noqa: F401
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import access_token, hash_password
from app.modules.auth.models import User
from app.modules.experience.models import Habit, Notification
from sqlalchemy import func, select
from sqlalchemy.engine import make_url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--users', type=int, default=1000)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    settings = get_settings()
    url = make_url(settings.database_url)
    if (settings.environment != 'loadtest' or url.host not in {'127.0.0.1', 'localhost', '::1'}
            or not (url.database or '').endswith('_loadtest') or not 1 <= args.users <= 10000):
        parser.error('Requires ENVIRONMENT=loadtest, a localhost *_loadtest database and 1–10000 users')
    # Refuse to replace a credential file or write into a populated database.
    with open(args.output, 'x', encoding='utf-8', opener=lambda path, flags: os.open(path, flags, 0o600)) as output, SessionLocal.begin() as db:
        if db.scalar(select(func.count(User.id))):
            parser.error('Fixture database must have no users; never reuse real app data')
        password_hash = hash_password(secrets.token_urlsafe(48))
        records = []
        for index in range(args.users):
            user = User(name=f'Load client {index}', email=f'load-{index}@example.invalid',
                        password_hash=password_hash, role='CLIENT', email_verified=True)
            db.add(user)
            db.flush()
            habits = [Habit(client_id=user.id, name=f'Test habit {n}') for n in range(3)]
            db.add_all(habits)
            db.add_all([Notification(user_id=user.id, title=f'Test notification {n}', body='Synthetic capacity fixture') for n in range(5)])
            db.flush()
            records.append({'id': user.id, 'token': access_token(user), 'habit_id': habits[0].id})
        json.dump(records, output)
    print(f'Created {args.users} synthetic clients with habits and notifications; private token file saved')


if __name__ == '__main__':
    main()
