"""Create the database and apply schema.sql without starting the server.

Usage:
    uv run python -m mall.init_db
"""

from sqlalchemy.exc import SQLAlchemyError

from mall import db


def main() -> None:
    try:
        config = db.settings()
        db.initialize()
    except db.DatabaseError as exc:
        raise SystemExit(str(exc)) from exc
    except SQLAlchemyError as exc:
        raise SystemExit(f"数据库初始化失败：{db.friendly_error(exc)}") from exc

    print(f"数据库已就绪：{config.database}（schema.sql 已应用）")


if __name__ == "__main__":
    main()