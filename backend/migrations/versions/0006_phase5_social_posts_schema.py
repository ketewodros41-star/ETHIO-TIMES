"""phase5_social_posts_schema

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-09 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None

def upgrade() -> None:
    bind = op.get_bind()
    
    if not bind.dialect.has_type(bind, 'social_platform'):
        sa.Enum('instagram', name='social_platform').create(bind)
        
    if not bind.dialect.has_type(bind, 'instagram_post_format'):
        sa.Enum('portrait', 'square', 'story', name='instagram_post_format').create(bind)
        
    if not bind.dialect.has_type(bind, 'social_post_status'):
        sa.Enum('draft', 'rendered', 'scheduled', 'published', 'failed', name='social_post_status').create(bind)
        
    if not bind.dialect.has_type(bind, 'visual_asset_status'):
        sa.Enum('generating', 'generated', 'approved', 'rejected', 'published', name='visual_asset_status').create(bind)
    
    op.create_table(
        'visual_assets',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('visual_strategy', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('provider', sa.String(length=64), server_default='mock', nullable=False),
        sa.Column('model', sa.String(length=128), nullable=True),
        sa.Column('style', sa.String(length=128), nullable=True),
        sa.Column('storage_path', sa.String(length=2048), nullable=True),
        sa.Column('storage_url', sa.String(length=2048), nullable=True),
        sa.Column('quality_score', sa.Integer(), nullable=True),
        sa.Column('quality_report', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('status', postgresql.ENUM('generating', 'generated', 'approved', 'rejected', 'published', name='visual_asset_status', create_type=False), server_default='generating', nullable=False),
        sa.Column('is_selected', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['news_events.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_visual_assets_event_id'), 'visual_assets', ['event_id'], unique=False)
    
    op.create_table(
        'social_posts',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('visual_asset_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('platform', postgresql.ENUM('instagram', name='social_platform', create_type=False), server_default='instagram', nullable=False),
        sa.Column('format', postgresql.ENUM('portrait', 'square', 'story', name='instagram_post_format', create_type=False), server_default='portrait', nullable=False),
        sa.Column('theme', sa.String(length=64), nullable=False),
        sa.Column('headline', sa.Text(), nullable=False),
        sa.Column('caption', sa.Text(), nullable=False),
        sa.Column('hashtags', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('source_attribution', sa.Text(), nullable=True),
        sa.Column('key_facts', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('media_path', sa.String(length=2048), nullable=True),
        sa.Column('media_url', sa.String(length=2048), nullable=True),
        sa.Column('status', postgresql.ENUM('draft', 'rendered', 'scheduled', 'published', 'failed', name='social_post_status', create_type=False), server_default='draft', nullable=False),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ig_media_id', sa.String(length=128), nullable=True),
        sa.Column('ig_post_id', sa.String(length=128), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('eligibility_snapshot', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['news_events.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['visual_asset_id'], ['visual_assets.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_social_posts_event_id'), 'social_posts', ['event_id'], unique=False)
    op.create_index(op.f('ix_social_posts_visual_asset_id'), 'social_posts', ['visual_asset_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_social_posts_visual_asset_id'), table_name='social_posts')
    op.drop_index(op.f('ix_social_posts_event_id'), table_name='social_posts')
    op.drop_table('social_posts')
    
    op.drop_index(op.f('ix_visual_assets_event_id'), table_name='visual_assets')
    op.drop_table('visual_assets')
    
    sa.Enum(name='social_platform').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='instagram_post_format').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='social_post_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='visual_asset_status').drop(op.get_bind(), checkfirst=True)
