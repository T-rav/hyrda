import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime, Integer, Text, select, delete, desc
from sqlalchemy.dialects.postgresql import UUID
from migrations.migration_manager import MigrationManager
from migrations.registry import register_migrations
import uuid

logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

class UserPrompt(Base):
    __tablename__ = "user_prompts"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    is_current: Mapped[bool] = mapped_column(nullable=False, default=True)

class UserPromptService:
    """Service for managing user system prompts with PostgreSQL persistence"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = create_async_engine(database_url, echo=False)
        self.async_session = async_sessionmaker(self.engine, expire_on_commit=False)
        self.migration_manager = None
        
    async def initialize(self):
        """Initialize database with migrations"""
        # Initialize migration manager
        self.migration_manager = MigrationManager(self.database_url)
        register_migrations(self.migration_manager)
        
        # Initialize migration system
        await self.migration_manager.initialize()
        
        # Apply any pending migrations
        await self.migration_manager.apply_migrations()
        
        logger.info("User prompt database initialized with migrations")
        
    async def close(self):
        """Close database connections"""
        if self.migration_manager:
            await self.migration_manager.close()
        await self.engine.dispose()
        
    async def set_user_prompt(self, user_id: str, prompt: str) -> None:
        """Set a new system prompt for a user"""
        async with self.async_session() as session:
            try:
                # Mark all existing prompts as not current
                await session.execute(
                    UserPrompt.__table__.update()
                    .where(UserPrompt.user_id == user_id)
                    .values(is_current=False)
                )
                
                # Add new prompt as current
                new_prompt = UserPrompt(
                    user_id=user_id,
                    prompt=prompt,
                    is_current=True
                )
                session.add(new_prompt)
                
                # Keep only last 5 prompts per user
                result = await session.execute(
                    select(UserPrompt)
                    .where(UserPrompt.user_id == user_id)
                    .order_by(desc(UserPrompt.created_at))
                    .offset(5)
                )
                old_prompts = result.scalars().all()
                
                for old_prompt in old_prompts:
                    await session.delete(old_prompt)
                
                await session.commit()
                logger.info(f"Set new prompt for user {user_id}")
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Error setting user prompt: {e}")
                raise
                
    async def get_user_prompt(self, user_id: str) -> Optional[str]:
        """Get the current system prompt for a user"""
        async with self.async_session() as session:
            try:
                result = await session.execute(
                    select(UserPrompt.prompt)
                    .where(UserPrompt.user_id == user_id, UserPrompt.is_current == True)
                )
                prompt = result.scalar_one_or_none()
                return prompt
                
            except Exception as e:
                logger.error(f"Error getting user prompt: {e}")
                return None
                
    async def get_user_prompt_history(self, user_id: str, limit: int = 5) -> List[Dict]:
        """Get user's prompt history"""
        async with self.async_session() as session:
            try:
                result = await session.execute(
                    select(UserPrompt)
                    .where(UserPrompt.user_id == user_id)
                    .order_by(desc(UserPrompt.created_at))
                    .limit(limit)
                )
                prompts = result.scalars().all()
                
                history = []
                for prompt in prompts:
                    preview = prompt.prompt[:50] + "..." if len(prompt.prompt) > 50 else prompt.prompt
                    history.append({
                        "prompt": prompt.prompt,
                        "preview": preview,
                        "timestamp": prompt.created_at.isoformat(),
                        "is_current": prompt.is_current
                    })
                
                return history
                
            except Exception as e:
                logger.error(f"Error getting user prompt history: {e}")
                return []
                
    async def reset_user_prompt(self, user_id: str) -> None:
        """Reset user to default prompt (delete all custom prompts)"""
        async with self.async_session() as session:
            try:
                await session.execute(
                    delete(UserPrompt).where(UserPrompt.user_id == user_id)
                )
                await session.commit()
                logger.info(f"Reset prompts for user {user_id}")
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Error resetting user prompts: {e}")
                raise