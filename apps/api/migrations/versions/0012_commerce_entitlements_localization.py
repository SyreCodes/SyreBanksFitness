"""Add commerce, entitlement and localization storage without changing existing access.

Revision ID: 0012
Revises: 0011
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exchange_rates",
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("target_currency", sa.String(length=3), nullable=False),
        sa.Column("rate", sa.Numeric(precision=24, scale=12), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("rate > 0", name="ck_exchange_rate_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("base_currency", "target_currency", name="uq_exchange_rate_pair"),
    )
    op.create_table(
        "carts",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_table(
        "entitlement_grants",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("resource_id", sa.String(length=36), server_default="", nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.String(length=100), nullable=False),
        sa.Column(
            "starts_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("granted_by", sa.String(length=36), nullable=True),
        sa.Column("reason", sa.String(length=1000), server_default="", nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["granted_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "key", "resource_id", "source_type", "source_id", name="uq_entitlement_source"
        ),
    )
    with op.batch_alter_table("entitlement_grants", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_entitlement_grants_key"), ["key"], unique=False)
        batch_op.create_index(batch_op.f("ix_entitlement_grants_user_id"), ["user_id"], unique=False)

    op.create_table(
        "cart_items",
        sa.Column("cart_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_cart_item_quantity"),
        sa.ForeignKeyConstraint(
            ["cart_id"],
            ["carts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cart_id", "product_id", name="uq_cart_product"),
    )
    with op.batch_alter_table("cart_items", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_cart_items_cart_id"), ["cart_id"], unique=False)

    op.create_table(
        "courses",
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("translations", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id"),
    )
    op.create_table(
        "digital_assets",
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("media_id", sa.String(length=36), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("asset_type", sa.String(length=40), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("(true)"), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["media_id"],
            ["media_assets.id"],
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("media_id"),
    )
    with op.batch_alter_table("digital_assets", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_digital_assets_product_id"), ["product_id"], unique=False)

    op.create_table(
        "product_prices",
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("country_code", sa.String(length=2), server_default="", nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("pricing_type", sa.String(length=30), server_default="one_time", nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("(true)"), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount_minor >= 0", name="ck_product_price_amount"),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "product_id", "country_code", "currency", "pricing_type", name="uq_product_market_price"
        ),
    )
    with op.batch_alter_table("product_prices", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_product_prices_product_id"), ["product_id"], unique=False)

    op.create_table(
        "product_translations",
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("locale", sa.String(length=10), nullable=False),
        sa.Column("title", sa.String(length=160), server_default="", nullable=False),
        sa.Column("short_description", sa.String(length=500), server_default="", nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("benefits", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("faq", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("seo_title", sa.String(length=200), server_default="", nullable=False),
        sa.Column("seo_description", sa.String(length=500), server_default="", nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "locale", name="uq_product_translation"),
    )
    with op.batch_alter_table("product_translations", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_product_translations_product_id"), ["product_id"], unique=False)

    op.create_table(
        "commerce_events",
        sa.Column("event", sa.String(length=80), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("product_id", sa.String(length=36), nullable=True),
        sa.Column("order_id", sa.String(length=36), nullable=True),
        sa.Column("session_id", sa.String(length=128), server_default="", nullable=False),
        sa.Column("details", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("commerce_events", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_commerce_events_event"), ["event"], unique=False)
        batch_op.create_index(batch_op.f("ix_commerce_events_order_id"), ["order_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_commerce_events_product_id"), ["product_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_commerce_events_user_id"), ["user_id"], unique=False)

    op.create_table(
        "course_modules",
        sa.Column("course_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("translations", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("course_modules", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_course_modules_course_id"), ["course_id"], unique=False)

    op.create_table(
        "order_items",
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("unit_amount_minor", sa.Integer(), nullable=False),
        sa.Column("total_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("snapshot", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("fx_snapshot", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_order_item_quantity"),
        sa.CheckConstraint("unit_amount_minor >= 0 AND total_minor >= 0", name="ck_order_item_amount"),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("order_items", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_order_items_order_id"), ["order_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_order_items_product_id"), ["product_id"], unique=False)

    op.create_table(
        "payment_intents",
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), server_default="AWAITING_MANUAL_PAYMENT", nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("provider_reference", sa.String(length=200), server_default="", nullable=False),
        sa.Column("checkout_url", sa.Text(), server_default="", nullable=False),
        sa.Column("details", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id"),
    )
    with op.batch_alter_table("payment_intents", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_payment_intents_status"), ["status"], unique=False)

    op.create_table(
        "course_lessons",
        sa.Column("module_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("type", sa.String(length=30), server_default="TEXT", nullable=False),
        sa.Column("body", sa.Text(), server_default="", nullable=False),
        sa.Column("media_id", sa.String(length=36), nullable=True),
        sa.Column("url", sa.String(length=1000), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("translations", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["media_id"],
            ["media_assets.id"],
        ),
        sa.ForeignKeyConstraint(
            ["module_id"],
            ["course_modules.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("course_lessons", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_course_lessons_module_id"), ["module_id"], unique=False)

    op.create_table(
        "lesson_progress",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("lesson_id", sa.String(length=36), nullable=False),
        sa.Column("completed", sa.Boolean(), server_default=sa.text("(false)"), nullable=False),
        sa.Column(
            "last_viewed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["lesson_id"],
            ["course_lessons.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "lesson_id", name="uq_user_lesson_progress"),
    )
    with op.batch_alter_table("lesson_progress", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_lesson_progress_lesson_id"), ["lesson_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_lesson_progress_user_id"), ["user_id"], unique=False)

    with op.batch_alter_table("blog_posts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("translations", sa.JSON(), server_default=sa.text("'{}'"), nullable=False)
        )

    with op.batch_alter_table("exercises", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("categories", sa.JSON(), server_default=sa.text("'[]'"), nullable=False)
        )
        batch_op.add_column(sa.Column("goal", sa.String(length=200), server_default="", nullable=False))
        batch_op.add_column(
            sa.Column("variations", sa.JSON(), server_default=sa.text("'[]'"), nullable=False)
        )
        batch_op.add_column(
            sa.Column("regressions", sa.JSON(), server_default=sa.text("'[]'"), nullable=False)
        )
        batch_op.add_column(
            sa.Column("progressions", sa.JSON(), server_default=sa.text("'[]'"), nullable=False)
        )

    with op.batch_alter_table("orders", schema=None) as batch_op:
        batch_op.add_column(sa.Column("country_code", sa.String(length=2), server_default="", nullable=False))
        batch_op.add_column(sa.Column("display_currency", sa.String(length=3), nullable=True))
        batch_op.add_column(sa.Column("settlement_currency", sa.String(length=3), nullable=True))
        batch_op.add_column(
            sa.Column("fx_snapshot", sa.JSON(), server_default=sa.text("'{}'"), nullable=False)
        )
        batch_op.add_column(sa.Column("checkout_key", sa.String(length=128), nullable=True))
        batch_op.create_unique_constraint("uq_order_checkout_key", ["client_id", "checkout_key"])

    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("provider", sa.String(length=40), server_default="flutterwave", nullable=False)
        )
        batch_op.add_column(sa.Column("confirmed_by", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("received_amount_minor", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("received_currency", sa.String(length=3), nullable=True))
        batch_op.add_column(sa.Column("method", sa.String(length=100), server_default="", nullable=False))
        batch_op.add_column(
            sa.Column("external_reference", sa.String(length=200), server_default="", nullable=False)
        )
        batch_op.add_column(sa.Column("internal_note", sa.Text(), server_default="", nullable=False))
        batch_op.create_foreign_key("fk_payments_confirmed_by", "users", ["confirmed_by"], ["id"])

    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("type", sa.String(length=30), server_default="COACHING", nullable=False)
        )
        batch_op.add_column(
            sa.Column("status", sa.String(length=30), server_default="PUBLISHED", nullable=False)
        )
        batch_op.add_column(sa.Column("slug", sa.String(length=200), nullable=True))
        batch_op.add_column(
            sa.Column("short_description", sa.String(length=500), server_default="", nullable=False)
        )
        batch_op.add_column(sa.Column("full_description", sa.Text(), server_default="", nullable=False))
        batch_op.add_column(sa.Column("cover_media_id", sa.String(length=36), nullable=True))
        batch_op.add_column(
            sa.Column("gallery_media_ids", sa.JSON(), server_default=sa.text("'[]'"), nullable=False)
        )
        batch_op.add_column(
            sa.Column("preview_url", sa.String(length=1000), server_default="", nullable=False)
        )
        batch_op.add_column(
            sa.Column("categories", sa.JSON(), server_default=sa.text("'[]'"), nullable=False)
        )
        batch_op.add_column(sa.Column("tags", sa.JSON(), server_default=sa.text("'[]'"), nullable=False))
        batch_op.add_column(sa.Column("benefits", sa.JSON(), server_default=sa.text("'[]'"), nullable=False))
        batch_op.add_column(
            sa.Column("requirements", sa.JSON(), server_default=sa.text("'[]'"), nullable=False)
        )
        batch_op.add_column(sa.Column("faq", sa.JSON(), server_default=sa.text("'[]'"), nullable=False))
        batch_op.add_column(
            sa.Column("included_content", sa.JSON(), server_default=sa.text("'[]'"), nullable=False)
        )
        batch_op.add_column(
            sa.Column("featured", sa.Boolean(), server_default=sa.text("(false)"), nullable=False)
        )
        batch_op.add_column(
            sa.Column("visibility", sa.String(length=30), server_default="PUBLIC", nullable=False)
        )
        batch_op.add_column(sa.Column("seo_title", sa.String(length=200), server_default="", nullable=False))
        batch_op.add_column(
            sa.Column("seo_description", sa.String(length=500), server_default="", nullable=False)
        )
        batch_op.create_index(batch_op.f("ix_products_status"), ["status"], unique=False)
        batch_op.create_unique_constraint("uq_products_slug", ["slug"])
        batch_op.create_foreign_key("fk_products_cover_media", "media_assets", ["cover_media_id"], ["id"])

    with op.batch_alter_table("programs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("translations", sa.JSON(), server_default=sa.text("'{}'"), nullable=False)
        )

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("locale", sa.String(length=10), server_default="en", nullable=False))
        batch_op.add_column(sa.Column("country_code", sa.String(length=2), server_default="", nullable=False))
        batch_op.add_column(sa.Column("currency", sa.String(length=3), server_default="", nullable=False))
        batch_op.add_column(
            sa.Column("billing_country_code", sa.String(length=2), server_default="", nullable=False)
        )

    # Preserve original order snapshots and timestamps, including historical prices.
    # Use migration-local table definitions so later model changes cannot affect replay.
    orders = sa.table(
        "orders",
        sa.column("id"),
        sa.column("product_id"),
        sa.column("amount_minor"),
        sa.column("currency"),
        sa.column("snapshot", sa.JSON()),
        sa.column("created_at"),
        sa.column("updated_at"),
    )
    items = sa.table(
        "order_items",
        sa.column("id"),
        sa.column("order_id"),
        sa.column("product_id"),
        sa.column("quantity"),
        sa.column("unit_amount_minor"),
        sa.column("total_minor"),
        sa.column("currency"),
        sa.column("snapshot", sa.JSON()),
        sa.column("created_at"),
        sa.column("updated_at"),
    )
    op.execute(
        items.insert().from_select(
            [
                "id",
                "order_id",
                "product_id",
                "quantity",
                "unit_amount_minor",
                "total_minor",
                "currency",
                "snapshot",
                "created_at",
                "updated_at",
            ],
            sa.select(
                orders.c.id,
                orders.c.id,
                orders.c.product_id,
                sa.literal(1),
                orders.c.amount_minor,
                orders.c.amount_minor,
                orders.c.currency,
                orders.c.snapshot,
                orders.c.created_at,
                orders.c.updated_at,
            ),
        )
    )
    products = sa.table("products", sa.column("id", sa.String()), sa.column("slug", sa.String()))
    op.execute(
        products.update().where(products.c.slug.is_(None)).values(slug=sa.literal("product-") + products.c.id)
    )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("billing_country_code")
        batch_op.drop_column("currency")
        batch_op.drop_column("country_code")
        batch_op.drop_column("locale")

    with op.batch_alter_table("programs", schema=None) as batch_op:
        batch_op.drop_column("translations")

    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.drop_constraint("fk_products_cover_media", type_="foreignkey")
        batch_op.drop_constraint("uq_products_slug", type_="unique")
        batch_op.drop_index(batch_op.f("ix_products_status"))
        batch_op.drop_column("seo_description")
        batch_op.drop_column("seo_title")
        batch_op.drop_column("visibility")
        batch_op.drop_column("featured")
        batch_op.drop_column("included_content")
        batch_op.drop_column("faq")
        batch_op.drop_column("requirements")
        batch_op.drop_column("benefits")
        batch_op.drop_column("tags")
        batch_op.drop_column("categories")
        batch_op.drop_column("preview_url")
        batch_op.drop_column("gallery_media_ids")
        batch_op.drop_column("cover_media_id")
        batch_op.drop_column("full_description")
        batch_op.drop_column("short_description")
        batch_op.drop_column("slug")
        batch_op.drop_column("status")
        batch_op.drop_column("type")

    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.drop_constraint("fk_payments_confirmed_by", type_="foreignkey")
        batch_op.drop_column("internal_note")
        batch_op.drop_column("external_reference")
        batch_op.drop_column("method")
        batch_op.drop_column("received_currency")
        batch_op.drop_column("received_amount_minor")
        batch_op.drop_column("confirmed_by")
        batch_op.drop_column("provider")

    with op.batch_alter_table("orders", schema=None) as batch_op:
        batch_op.drop_constraint("uq_order_checkout_key", type_="unique")
        batch_op.drop_column("checkout_key")
        batch_op.drop_column("fx_snapshot")
        batch_op.drop_column("settlement_currency")
        batch_op.drop_column("display_currency")
        batch_op.drop_column("country_code")

    with op.batch_alter_table("exercises", schema=None) as batch_op:
        batch_op.drop_column("progressions")
        batch_op.drop_column("regressions")
        batch_op.drop_column("variations")
        batch_op.drop_column("goal")
        batch_op.drop_column("categories")

    with op.batch_alter_table("blog_posts", schema=None) as batch_op:
        batch_op.drop_column("translations")

    with op.batch_alter_table("lesson_progress", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_lesson_progress_user_id"))
        batch_op.drop_index(batch_op.f("ix_lesson_progress_lesson_id"))

    op.drop_table("lesson_progress")
    with op.batch_alter_table("course_lessons", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_course_lessons_module_id"))

    op.drop_table("course_lessons")
    with op.batch_alter_table("payment_intents", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_payment_intents_status"))

    op.drop_table("payment_intents")
    with op.batch_alter_table("order_items", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_order_items_product_id"))
        batch_op.drop_index(batch_op.f("ix_order_items_order_id"))

    op.drop_table("order_items")
    with op.batch_alter_table("course_modules", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_course_modules_course_id"))

    op.drop_table("course_modules")
    with op.batch_alter_table("commerce_events", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_commerce_events_user_id"))
        batch_op.drop_index(batch_op.f("ix_commerce_events_product_id"))
        batch_op.drop_index(batch_op.f("ix_commerce_events_order_id"))
        batch_op.drop_index(batch_op.f("ix_commerce_events_event"))

    op.drop_table("commerce_events")
    with op.batch_alter_table("product_translations", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_product_translations_product_id"))

    op.drop_table("product_translations")
    with op.batch_alter_table("product_prices", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_product_prices_product_id"))

    op.drop_table("product_prices")
    with op.batch_alter_table("digital_assets", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_digital_assets_product_id"))

    op.drop_table("digital_assets")
    op.drop_table("courses")
    with op.batch_alter_table("cart_items", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_cart_items_cart_id"))

    op.drop_table("cart_items")
    with op.batch_alter_table("entitlement_grants", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_entitlement_grants_user_id"))
        batch_op.drop_index(batch_op.f("ix_entitlement_grants_key"))

    op.drop_table("entitlement_grants")
    op.drop_table("carts")
    op.drop_table("exchange_rates")
    # ### end Alembic commands ###
