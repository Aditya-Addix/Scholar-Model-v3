from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class VaultItem(Base):
    __tablename__ = "vault_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    concept_tags: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    date_added: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    ease_factor: Mapped[float] = mapped_column(Float, nullable=False, default=2.5)
    interval: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_review_date: Mapped[datetime] = mapped_column(DateTime, nullable=True, default=datetime.utcnow)


class DailyAnalytics(Base):
    __tablename__ = "daily_analytics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    problems_solved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    physics_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    math_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    is_premium: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class UserStats(Base):
    __tablename__ = "user_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, default=1, index=True)
    current_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_active_date: Mapped[date | None] = mapped_column(nullable=True)
    total_solved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class BlackBox(Base):
    __tablename__ = "black_box"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, default=1, index=True)
    exam_type: Mapped[str] = mapped_column(String(32), nullable=False, default="General")
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    concept_tags: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    date_added: Mapped[date] = mapped_column(nullable=False, default=date.today)


DATABASE_PATH = Path(__file__).resolve().parent / "addix_data.db"
DATABASE_URL = "sqlite:///./addix_data.db"
ASYNC_DATABASE_URL = "sqlite+aiosqlite:///./addix_data.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 15},
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)

async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 15},
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)


def initialize_sqlite_schema() -> None:
    Base.metadata.create_all(bind=engine)


async def init_db() -> None:
    initialize_sqlite_schema()
    async with async_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(_ensure_vault_item_schema_sync)
        await connection.run_sync(_ensure_user_schema_sync)


def _ensure_vault_item_schema_sync(connection) -> None:
    inspector = inspect(connection)
    if "vault_items" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("vault_items")}
    alter_statements: list[str] = []

    if "ease_factor" not in existing_columns:
        alter_statements.append("ALTER TABLE vault_items ADD COLUMN ease_factor FLOAT NOT NULL DEFAULT 2.5")
    if "interval" not in existing_columns:
        alter_statements.append("ALTER TABLE vault_items ADD COLUMN interval INTEGER NOT NULL DEFAULT 0")
    if "next_review_date" not in existing_columns:
        alter_statements.append("ALTER TABLE vault_items ADD COLUMN next_review_date DATETIME")

    if not alter_statements:
        return

    for statement in alter_statements:
        connection.execute(text(statement))

    if "next_review_date" not in existing_columns:
        connection.execute(text("UPDATE vault_items SET next_review_date = date_added WHERE next_review_date IS NULL"))


def _ensure_user_schema_sync(connection) -> None:
    inspector = inspect(connection)
    table_names = set(inspector.get_table_names())

    if "user_stats" in table_names:
        stats_columns = {column["name"] for column in inspector.get_columns("user_stats")}
        if "user_id" not in stats_columns:
            connection.execute(text("ALTER TABLE user_stats ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1"))

    if "black_box" in table_names:
        black_box_columns = {column["name"] for column in inspector.get_columns("black_box")}
        if "user_id" not in black_box_columns:
            connection.execute(text("ALTER TABLE black_box ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1"))

    if "users" in table_names:
        default_user = connection.execute(text("SELECT id FROM users WHERE id = 1 LIMIT 1")).fetchone()
        if default_user is None:
            connection.execute(
                text(
                    "INSERT INTO users (id, email, hashed_password, is_premium) "
                    "VALUES (1, 'default@addix.local', '', 0)"
                )
            )


def parse_tags(raw_tags: str) -> list[str]:
    try:
        parsed = json.loads(raw_tags)
    except Exception:
        return []
    if not isinstance(parsed, list):
        return []
    tags: list[str] = []
    for tag in parsed:
        value = str(tag or "").strip()
        if value:
            tags.append(value)
    return tags[:8]
