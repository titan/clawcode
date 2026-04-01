"""Database connection management.

This module handles database connections, session management,
and initialization.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .models import Base


def _sqlite_add_message_deleted_at_column(sync_conn) -> None:
    """Add messages.deleted_at if missing (existing SQLite DBs)."""
    r = sync_conn.execute(text("PRAGMA table_info(messages)"))
    cols = {row[1] for row in r.fetchall()}
    if "deleted_at" not in cols:
        sync_conn.execute(text("ALTER TABLE messages ADD COLUMN deleted_at INTEGER"))


class Database:
    """Database connection manager.

    This class manages the database engine and provides
    async sessions for database operations.
    """

    def __init__(self, database_path: str | Path) -> None:
        """Initialize the database manager.

        Args:
            database_path: Path to the SQLite database file
        """
        self._database_path = Path(database_path)
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    @property
    def engine(self) -> AsyncEngine:
        """Get the database engine.

        Returns:
            The SQLAlchemy async engine

        Raises:
            RuntimeError: If the database is not initialized
        """
        if self._engine is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Get the session factory.

        Returns:
            The async session factory

        Raises:
            RuntimeError: If the database is not initialized
        """
        if self._session_factory is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._session_factory

    async def initialize(self) -> None:
        """Initialize the database.

        Creates the database engine, sets up the session factory,
        and creates all tables if they don't exist.
        """
        # Ensure the database directory exists
        self._database_path.parent.mkdir(parents=True, exist_ok=True)

        # Create the async engine
        database_url = f"sqlite+aiosqlite:///{self._database_path}"
        self._engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )

        # Create the session factory
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Create all tables
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(_sqlite_add_message_deleted_at_column)

    async def close(self) -> None:
        """Close the database connection.

        Disposes of the engine and all connections.
        """
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a database session.

        Yields:
            An async database session

        Example:
            async with db.session() as session:
                result = await session.execute(select(Session))
        """
        if self._session_factory is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def health_check(self) -> bool:
        """Check if the database is healthy.

        Returns:
            True if the database is accessible, False otherwise
        """
        try:
            async with self.session() as session:
                # Simple query to test connection
                from sqlalchemy import text

                await session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False


# Global database instance
_db: Database | None = None


def get_database() -> Database:
    """Get the global database instance.

    Returns:
        The database instance

    Raises:
        RuntimeError: If the database is not initialized
    """
    global _db
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _db


async def init_database(database_path: str | Path) -> Database:
    """Initialize the global database instance.

    Args:
        database_path: Path to the SQLite database file

    Returns:
        The initialized database instance
    """
    global _db
    _db = Database(database_path)
    await _db.initialize()
    return _db


async def close_database() -> None:
    """Close the global database instance."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None
