"""Generate unique development credentials without overwriting existing configuration."""
from pathlib import Path
import secrets

root = Path(__file__).resolve().parent.parent
destination = root / ".env"
if destination.exists():
    raise SystemExit(".env already exists; refusing to overwrite your configuration.")
password = secrets.token_urlsafe(24)
content = (root / ".env.example").read_text()
replacements = {
    "replace-with-a-unique-secret-at-least-32-characters": secrets.token_urlsafe(48),
    "replace-with-a-unique-database-password": password,
    "replace-with-a-unique-storage-password": secrets.token_urlsafe(32),
    "SEED_ADMIN_PASSWORD=": f"SEED_ADMIN_PASSWORD={secrets.token_urlsafe(18)}",
    "SEED_CLIENT_PASSWORD=": f"SEED_CLIENT_PASSWORD={secrets.token_urlsafe(18)}",
}
for source, target in replacements.items():
    content = content.replace(source, target)
destination.write_text(content)
destination.chmod(0o600)
print("Created .env with unique local secrets. Seed credentials are in SEED_ADMIN_PASSWORD and SEED_CLIENT_PASSWORD.")
