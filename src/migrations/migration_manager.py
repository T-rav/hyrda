import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, String, delete, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

logger = logging.getLogger(__name__)


class MigrationBase(DeclarativeBase):
    pass


class MigrationHistory(MigrationBase):
    __tablename__ = "migration_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class Migration:
    """Base class for database migrations"""

    def __init__(self, version: str, name: str):
        self.version = version
        self.name = name

    async def up(self, session: AsyncSession) -> None:
        """Apply the migration"""
        raise NotImplementedError("Migration must implement up() method")

    async def down(self, session: AsyncSession) -> None:
        """Rollback the migration (optional)"""
        logger.warning(f"Migration {self.version} does not support rollback")


class MigrationManager:
    """Manages database migrations"""

    def __init__(self, database_url: str):
        self.engine = create_async_engine(database_url, echo=False)
        self.async_session = async_sessionmaker(self.engine, expire_on_commit=False)
        self.migrations: list[Migration] = []

    def add_migration(self, migration: Migration) -> None:
        """Add a migration to be managed"""
        self.migrations.append(migration)
        # Sort migrations by version
        self.migrations.sort(key=lambda m: m.version)

    async def initialize(self) -> None:
        """Initialize migration system by creating migration_history table"""
        async with self.engine.begin() as conn:
            await conn.run_sync(MigrationBase.metadata.create_all)
        logger.info("Migration system initialized")

    async def get_applied_migrations(self) -> list[str]:
        """Get list of applied migration versions"""
        async with self.async_session() as session:
            try:
                result = await session.execute(
                    select(MigrationHistory.version).order_by(
                        MigrationHistory.applied_at
                    )
                )
                return list(result.scalars())
            except Exception as e:
                # If migration_history table doesn't exist, return empty list
                logger.debug(f"Could not get migration history: {e}")
                return []

    async def apply_migrations(self) -> None:
        """Apply all pending migrations"""
        applied = await self.get_applied_migrations()
        pending = [m for m in self.migrations if m.version not in applied]

        if not pending:
            logger.info("No pending migrations")
            return

        logger.info(f"Applying {len(pending)} pending migrations")

        for migration in pending:
            await self._apply_migration(migration)

    async def _apply_migration(self, migration: Migration) -> None:
        """Apply a single migration"""
        async with self.async_session() as session:
            try:
                logger.info(f"Applying migration {migration.version}: {migration.name}")

                # Apply the migration
                await migration.up(session)

                # Record the migration as applied
                history_entry = MigrationHistory(
                    version=migration.version, name=migration.name
                )
                session.add(history_entry)

                await session.commit()
                logger.info(f"Successfully applied migration {migration.version}")

            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to apply migration {migration.version}: {e}")
                raise

    async def rollback_migration(self, version: str) -> None:
        """Rollback a specific migration"""
        migration = next((m for m in self.migrations if m.version == version), None)
        if not migration:
            raise ValueError(f"Migration {version} not found")

        async with self.async_session() as session:
            try:
                logger.info(
                    f"Rolling back migration {migration.version}: {migration.name}"
                )

                # Rollback the migration
                await migration.down(session)

                # Remove from migration history
                # Remove from migration history using delete query
                stmt = delete(MigrationHistory).where(
                    MigrationHistory.version == version
                )
                await session.execute(stmt)

                await session.commit()
                logger.info(f"Successfully rolled back migration {migration.version}")

            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to rollback migration {migration.version}: {e}")
                raise

    async def get_migration_status(self) -> dict[str, Any]:
        """Get current migration status"""
        applied = await self.get_applied_migrations()
        pending = [m.version for m in self.migrations if m.version not in applied]

        return {
            "total_migrations": len(self.migrations),
            "applied_count": len(applied),
            "pending_count": len(pending),
            "applied_migrations": applied,
            "pending_migrations": pending,
            "latest_applied": applied[-1] if applied else None,
        }

    async def close(self) -> None:
        """Close database connections"""
        await self.engine.dispose()
