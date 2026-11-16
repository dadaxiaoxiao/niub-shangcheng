import logging
import os
import re
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple
from urllib.parse import unquote, urlsplit

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine, URL
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker


logger = logging.getLogger(__name__)

DEFAULT_SCHEMA_FILE = Path(__file__).resolve().parents[2] / "schema.sql"
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
_DATABASE_NAME = re.compile(r"^[A-Za-z0-9_]+$")
_DATABASE_STATEMENT = re.compile(r"^(?:CREATE\s+DATABASE|USE)\b", re.IGNORECASE)

INIT_HINT = (
    "数据库尚未初始化，会话历史功能不可用。请任选一种方式完成初始化：\n"
    "  1. 在 mall/.env 配置 MALL_DB_URL，然后在 mall 目录执行："
    "uv run python -m mall.init_db\n"
    "  2. 用 MySQL 客户端执行 mall/schema.sql\n"
    "详见 README 的「从零开始：完整运行教程」。mall 其余接口不受影响。"
)

_RETRY_SECONDS = 5.0
_lock = threading.Lock()
_ready = False
_last_error: str | None = None
_last_attempt_at = 0.0

_engine_lock = threading.Lock()
_engine: Engine | None = None
_engine_url: URL | None = None
_session_factory: sessionmaker[Session] | None = None


class DatabaseError(RuntimeError):
    """A safe, user-facing database configuration error."""


def load_env() -> None:
    """Load mall/.env by package path so startup does not depend on cwd."""
    load_dotenv(ENV_FILE, override=False)


load_env()


class DatabaseSettings(NamedTuple):
    host: str
    port: int
    user: str
    password: str
    database: str


def settings() -> DatabaseSettings:
    dsn = os.getenv("MALL_DB_URL", "").strip()
    if not dsn:
        raise DatabaseError("数据库未配置：请在 mall/.env 中设置 MALL_DB_URL。")

    parsed = urlsplit(dsn)
    if parsed.scheme not in {"mysql", "mysql+pymysql"}:
        raise DatabaseError("MALL_DB_URL 必须以 mysql:// 开头。")

    database = unquote(parsed.path.lstrip("/"))
    if not _DATABASE_NAME.fullmatch(database):
        raise DatabaseError("MALL_DB_URL 中的数据库名无效。")

    return DatabaseSettings(
        host=parsed.hostname or "127.0.0.1",
        port=parsed.port or 3306,
        user=unquote(parsed.username or ""),
        password=unquote(parsed.password or ""),
        database=database,
    )


def _url(include_database: bool = True) -> URL:
    config = settings()
    return URL.create(
        "mysql+pymysql",
        username=config.user or None,
        password=config.password or None,
        host=config.host,
        port=config.port,
        database=config.database if include_database else None,
        query={"charset": "utf8mb4"},
    )


def engine() -> Engine:
    """Return the shared SQLAlchemy engine, rebuilding it if the DSN changed."""
    global _engine, _engine_url, _session_factory

    url = _url()
    with _engine_lock:
        if _engine is None or _engine_url != url:
            if _engine is not None:
                _engine.dispose()
            _engine = create_engine(url, pool_pre_ping=True, pool_recycle=1800)
            _engine_url = url
            _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
        return _engine


@contextmanager
def session() -> Iterator[Session]:
    """Open an ORM session; uncommitted work rolls back when the block exits."""
    engine()
    factory = _session_factory
    if factory is None:
        raise DatabaseError("数据库会话尚未就绪。")
    with factory() as session:
        yield session


def split_statements(sql: str) -> list[str]:
    """Split a DDL script on semicolons, ignoring full-line SQL comments."""
    lines = [
        line
        for line in sql.splitlines()
        if line.strip() and not line.strip().startswith("--")
    ]
    return [part.strip() for part in "\n".join(lines).split(";") if part.strip()]


def _is_database_statement(statement: str) -> bool:
    """Database-level statements are only for manual runs of schema.sql."""
    return _DATABASE_STATEMENT.match(statement) is not None


def initialize() -> None:
    """Create the database if needed, then apply schema.sql."""
    config = settings()

    server_engine = create_engine(
        _url(include_database=False),
        isolation_level="AUTOCOMMIT",
    )
    try:
        with server_engine.connect() as connection:
            connection.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS `{config.database}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
                )
            )
    finally:
        server_engine.dispose()

    schema_path = Path(
        os.getenv("MALL_SCHEMA_FILE", str(DEFAULT_SCHEMA_FILE))
    ).expanduser()
    if not schema_path.is_absolute():
        schema_path = Path.cwd() / schema_path

    try:
        schema_sql = schema_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise DatabaseError("无法读取数据库 schema 文件。") from exc

    with engine().begin() as connection:
        for statement in split_statements(schema_sql):
            if _is_database_statement(statement):
                # The script is runnable by hand; the service keeps
                # MALL_DB_URL authoritative instead.
                continue
            connection.execute(text(statement))


def friendly_error(exc: Exception) -> str:
    if isinstance(exc, DatabaseError):
        return str(exc)

    original = exc.orig if isinstance(exc, DBAPIError) else exc
    code = original.args[0] if getattr(original, "args", None) else None
    if isinstance(code, int):
        known = {
            1044: "MySQL 账号没有访问该数据库的权限。",
            1045: "MySQL 拒绝访问：请检查 MALL_DB_URL 中的用户名和密码。",
            1049: "数据库不存在：请先执行初始化。",
            2003: "无法连接 MySQL：请确认 MySQL 已启动，并检查主机和端口。",
        }
        if code in known:
            return known[code]

    return "数据库不可用：请检查 MALL_DB_URL 和 MySQL 状态。"


def _verify_schema() -> None:
    """Check that the database and tables exist, without changing anything."""
    tables = set(inspect(engine()).get_table_names())
    if not {"conversations", "messages"} <= tables:
        raise DatabaseError(
            "数据库尚未初始化（缺少 conversations 或 messages 表）。"
        )


def ensure_ready() -> bool:
    """Verify the schema once and cache the result. Never runs DDL."""
    global _ready, _last_error, _last_attempt_at

    with _lock:
        if _ready:
            return True

        # Re-read .env on every retry so a freshly created config is picked up.
        load_env()

        now = time.monotonic()
        if _last_attempt_at and now - _last_attempt_at < _RETRY_SECONDS:
            return False

        _last_attempt_at = now
        try:
            _verify_schema()
        except (DatabaseError, SQLAlchemyError) as exc:
            message = friendly_error(exc)
            if message != _last_error:
                logger.error("[mall] %s", message)
                logger.error("[mall] %s", INIT_HINT)
            _last_error = message
            return False

        _ready = True
        _last_error = None
        logger.info("[mall] 数据库已就绪：%s", settings().database)
        return True


def status() -> tuple[bool, str | None]:
    return _ready, _last_error


def unavailable_detail() -> str:
    reason = _last_error or "数据库尚未初始化。"
    return (
        f"{reason} 请在 mall 目录执行 `uv run python -m mall.init_db`，"
        "或用 MySQL 客户端执行 mall/schema.sql，然后重试。"
    )


def utc_now() -> datetime:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return now.replace(microsecond=(now.microsecond // 1000) * 1000)


def to_iso(value: datetime) -> str:
    return (
        value.replace(tzinfo=timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )