"""Exercise the real migration history, independently of ORM create_all fixtures."""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import sqlalchemy as sa

API_ROOT = Path(__file__).resolve().parents[1]
STAMP = datetime(2025, 1, 1, 12)


def migrate(database: Path, *arguments: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=API_ROOT,
        env={**os.environ, "DATABASE_URL": f"sqlite:///{database}", "ENVIRONMENT": "test"},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def legacy_rows() -> dict[str, dict[str, Any]]:
    common = {"created_at": STAMP, "updated_at": STAMP}
    rows = {
        "users": dict(
            id="legacy-user",
            name="Existing member",
            email="legacy@example.test",
            password_hash="unused",
            role="CLIENT",
            active=True,
            email_verified=True,
            token_version=2,
            timezone="Africa/Kigali",
            status="ACTIVE",
            goal="Strength",
            demo=False,
        ),
        "products": dict(
            id="legacy-product",
            name="Original coaching",
            description="Preserved description",
            price_minor=3500,
            currency="USD",
            billing_interval="monthly",
            features=["Coaching"],
            entitlements={"exercise_library": True},
            active=True,
            demo=False,
        ),
        "media_assets": dict(
            id="legacy-media",
            owner_id="legacy-user",
            storage_key="exercise/demo.mp4",
            content_type="video/mp4",
            size=123,
            caption="Existing video",
            purpose="exercise",
            public=True,
            upload_id="original-upload",
        ),
        "exercises": dict(
            id="legacy-exercise",
            name="Squat",
            muscle_group="Legs",
            equipment="Bodyweight",
            difficulty="Beginner",
            description="Old movement",
            instructions="Existing instructions",
            coach_cues=["Brace"],
            video_media_id="legacy-media",
            published=True,
            owner_id="legacy-user",
            demo=False,
        ),
        "orders": dict(
            id="legacy-order",
            client_id="legacy-user",
            product_id="legacy-product",
            snapshot={"name": "Price at purchase", "price_minor": 2500},
            amount_minor=2500,
            currency="USD",
            status="PAID",
            reference="SBF-legacy",
        ),
        "payments": dict(
            id="legacy-payment",
            order_id="legacy-order",
            provider_transaction_id="verified-legacy",
            status="VERIFIED",
            amount_minor=2500,
            currency="USD",
        ),
        "subscriptions": dict(
            id="legacy-subscription",
            client_id="legacy-user",
            product_id="legacy-product",
            order_id="legacy-order",
            status="ACTIVE",
            current_period_start=STAMP,
            current_period_end=datetime(2027, 1, 1),
            entitlements={"exercise_library": True},
        ),
        "invoices": dict(
            id="legacy-invoice",
            client_id="legacy-user",
            order_id="legacy-order",
            number="INV-legacy",
            amount_minor=2500,
            currency="USD",
            status="PAID",
            issued_at=STAMP,
            items=[{"name": "Price at purchase", "amount_minor": 2500}],
        ),
    }
    return {name: {**common, **row} for name, row in rows.items()}


def test_commerce_migration_fresh_upgrade_matches_models(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    migrate(database, "upgrade", "head")
    migrate(database, "upgrade", "head")
    migrate(database, "check")
    engine = sa.create_engine(f"sqlite:///{database}")
    try:
        tables = set(sa.inspect(engine).get_table_names())
        assert {
            "order_items",
            "payment_intents",
            "entitlement_grants",
            "product_translations",
            "product_prices",
            "digital_assets",
            "carts",
            "cart_items",
            "courses",
            "course_modules",
            "course_lessons",
            "lesson_progress",
            "exchange_rates",
            "commerce_events",
        } <= tables
    finally:
        engine.dispose()


def test_commerce_migration_preserves_history_and_legacy_writes(tmp_path: Path) -> None:
    database = tmp_path / "historical.db"
    migrate(database, "upgrade", "0011")
    engine = sa.create_engine(f"sqlite:///{database}")
    old_metadata = sa.MetaData()
    old_metadata.reflect(engine)
    rows = legacy_rows()
    with engine.begin() as connection:
        for name, row in rows.items():
            connection.execute(old_metadata.tables[name].insert().values(**row))
        before = {
            name: dict(connection.execute(sa.select(old_metadata.tables[name])).mappings().one())
            for name in rows
        }
    engine.dispose()

    migrate(database, "upgrade", "head")
    migrate(database, "check")
    engine = sa.create_engine(f"sqlite:///{database}")
    metadata = sa.MetaData()
    metadata.reflect(engine)
    try:
        with engine.begin() as connection:
            for name, original in before.items():
                current = dict(connection.execute(sa.select(metadata.tables[name])).mappings().one())
                assert {key: current[key] for key in original} == original
            item = connection.execute(sa.select(metadata.tables["order_items"])).mappings().one()
            assert item["order_id"] == "legacy-order"
            assert item["product_id"] == "legacy-product"
            assert item["quantity"] == 1
            assert item["unit_amount_minor"] == item["total_minor"] == 2500
            assert item["snapshot"] == rows["orders"]["snapshot"]
            assert item["created_at"] == item["updated_at"] == STAMP
            assert item["fx_snapshot"] == {}
            # Simulate the previous API release: insert only pre-0012 columns.
            for name in ["users", "products", "orders", "payments", "exercises"]:
                row = {**rows[name], "id": f"second-{name}"}
                if name == "users":
                    row["email"] = "second@example.test"
                elif name == "orders":
                    row["reference"] = "SBF-second"
                elif name == "payments":
                    row.update(order_id="second-orders", provider_transaction_id="verified-second")
                elif name == "exercises":
                    row["video_media_id"] = None
                connection.execute(old_metadata.tables[name].insert().values(**row))
            product = (
                connection.execute(
                    sa.select(metadata.tables["products"]).where(
                        metadata.tables["products"].c.id == "second-products"
                    )
                )
                .mappings()
                .one()
            )
            assert product["type"] == "COACHING" and product["status"] == "PUBLISHED"
            assert product["gallery_media_ids"] == [] and product["slug"] is None
            user = (
                connection.execute(
                    sa.select(metadata.tables["users"]).where(metadata.tables["users"].c.id == "second-users")
                )
                .mappings()
                .one()
            )
            assert user["locale"] == "en" and user["country_code"] == ""
            assert connection.execute(sa.text("PRAGMA foreign_key_check")).all() == []
    finally:
        engine.dispose()
