"""Wait for PostgreSQL to accept connections before app startup."""

from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.database import engine


async def wait_for_db(max_attempts: int = 30, delay_seconds: int = 2) -> None:
    """Poll the database until a simple query succeeds."""
    for attempt in range(1, max_attempts + 1):
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return
        except OperationalError:
            if attempt == max_attempts:
                raise
            print(f"Database not ready yet (attempt {attempt}/{max_attempts}). Retrying in {delay_seconds}s...")
            await asyncio.sleep(delay_seconds)


if __name__ == "__main__":
    asyncio.run(wait_for_db())
