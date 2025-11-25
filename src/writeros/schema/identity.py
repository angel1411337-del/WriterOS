"""
Identity and Vault Management Schema.

Supports Hybrid Architecture:
- V1 (Obsidian Local): Filesystem-based with auto-login
- V2 (Cloud SaaS): Database-based with authentication

Design Philosophy: "Headless Logic"
The backend is agnostic to storage location. Agents interact with
ContentProvider interface, not directly with files or database.
"""
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime
from enum import Enum
from sqlmodel import Field, Relationship
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB

from .base import UUIDMixin, TimestampMixin


class ConnectionType(str, Enum):
    """How the vault connects to its content."""
    LOCAL_OBSIDIAN = "obsidian_local"  # V1: Reads local disk via Docker Mount
    CLOUD_HOSTED = "cloud_hosted"      # V2: SaaS only, database storage


class SubscriptionTier(str, Enum):
    """Pricing tiers for SaaS model."""
    FREE = "free"         # Limited features
    MINI = "mini"         # $25/mo - Personal use
    PRO = "pro"           # $65/mo - Professional writer
    BYOK = "byok"         # $20/mo - Bring Your Own Key (OpenAI/Anthropic)


class User(UUIDMixin, TimestampMixin, table=True):
    """
    Writer/Author identity.

    V1 (Local): Auto-created "Admin User" on startup (no login required)
    V2 (SaaS): Email/password authentication with JWT
    """
    __tablename__ = "users"

    email: str = Field(unique=True, index=True)
    username: str = Field(unique=True, index=True)
    display_name: Optional[str] = None

    # Auth (Optional for LOCAL mode)
    hashed_password: Optional[str] = None
    tier: SubscriptionTier = Field(default=SubscriptionTier.FREE)

    # Auth Provider (local, google, github, etc)
    auth_provider: str = "local"
    auth_id: Optional[str] = None  # External provider ID

    # User preferences
    preferences: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB)
    )

    # Relationships
    vaults: List["Vault"] = Relationship(back_populates="owner")


class Vault(UUIDMixin, TimestampMixin, table=True):
    """
    Story project container.

    Hybrid Model:
    - LOCAL_OBSIDIAN: Vault mirrors a filesystem directory
    - CLOUD_HOSTED: Vault is purely database-backed

    The ContentProvider pattern abstracts this difference.
    """
    __tablename__ = "vaults"

    name: str
    description: Optional[str] = None

    # Ownership (Nullable for migration compatibility)
    owner_id: Optional[UUID] = Field(
        default=None,
        foreign_key="users.id",
        index=True
    )

    # The Hybrid Logic
    connection_type: ConnectionType = Field(default=ConnectionType.LOCAL_OBSIDIAN)

    # If LOCAL_OBSIDIAN: Required path to Obsidian vault
    # If CLOUD_HOSTED: None (content lives in database)
    local_system_path: Optional[str] = None

    # Settings
    default_model: str = "gpt-4"
    settings: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB)
    )

    # Cached Statistics (updated by background jobs)
    entity_count: int = 0
    scene_count: int = 0
    word_count: int = 0
    last_indexed_at: Optional[datetime] = None

    # Relationships
    owner: Optional[User] = Relationship(back_populates="vaults")


# Future: Collaboration features (not implemented yet)
# class VaultMember(UUIDMixin, TimestampMixin, table=True):
#     """
#     Team collaboration model.
#     Allows multiple users to access a single vault with different permissions.
#     """
#     __tablename__ = "vault_members"
#
#     vault_id: UUID = Field(foreign_key="vaults.id", index=True)
#     user_id: UUID = Field(foreign_key="users.id", index=True)
#     role: str = "viewer"  # owner, editor, viewer, commenter
#
#     invited_by: UUID = Field(foreign_key="users.id")
#     invited_at: datetime = Field(default_factory=datetime.utcnow)
#     accepted_at: Optional[datetime] = None
