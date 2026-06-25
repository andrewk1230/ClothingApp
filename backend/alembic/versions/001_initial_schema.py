"""Initial schema with listings, rate_limits, search_history, saved_items

Revision ID: 001
Revises: None
Create Date: 2025-06-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "listings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("platform_id", sa.String(255), nullable=False, unique=True),
        sa.Column("listing_url", sa.Text, nullable=False),
        sa.Column("image_url", sa.Text, nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=True),
        sa.Column("currency", sa.String(3), server_default="USD"),
        sa.Column("size", sa.String(50), nullable=True),
        sa.Column("condition", sa.String(50), nullable=True),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.execute("ALTER TABLE listings ADD COLUMN embedding vector(512) NOT NULL")
    op.execute(
        "CREATE INDEX idx_listings_embedding ON listings "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )
    op.create_index("idx_listings_active", "listings", ["is_active"], postgresql_where=sa.text("is_active = true"))
    op.create_index("idx_listings_platform_id", "listings", ["platform_id"])

    op.create_table(
        "rate_limits",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("key_type", sa.String(10), nullable=False),
        sa.Column("search_count", sa.Integer, server_default="0"),
        sa.Column("window_date", sa.Date, server_default=sa.text("CURRENT_DATE")),
        sa.UniqueConstraint("key", "window_date"),
    )

    op.create_table(
        "search_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("bbox", JSONB, nullable=True),
        sa.Column("result_ids", sa.ARRAY(UUID(as_uuid=True)), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_search_history_user", "search_history", ["user_id", sa.text("created_at DESC")])

    op.create_table(
        "saved_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("listing_id", UUID(as_uuid=True), sa.ForeignKey("listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "listing_id"),
    )
    op.create_index("idx_saved_items_user", "saved_items", ["user_id", sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_table("saved_items")
    op.drop_table("search_history")
    op.drop_table("rate_limits")
    op.drop_table("listings")
    op.execute("DROP EXTENSION IF EXISTS vector")
