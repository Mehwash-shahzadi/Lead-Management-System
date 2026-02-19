from sqlalchemy.ext.asyncio import AsyncSession


class BaseRepository:
    """Thin base class that holds the database session.

    Every concrete repository receives an ``AsyncSession`` at
    construction time so that multiple repositories can share the same
    unit-of-work within a single request.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def flush(self) -> None:
        """Flush pending changes without committing."""
        await self._db.flush()

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._db.commit()

    async def rollback(self) -> None:
        """Roll back the current transaction."""
        await self._db.rollback()
