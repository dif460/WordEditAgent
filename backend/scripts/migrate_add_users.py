"""一次性迁移：将 tasks.user_id 重命名为 session_id，移除 users 表。"""
from sqlalchemy import text

from app.database import engine, Base


def migrate() -> None:
    """重命名 user_id → session_id 列，删除 users 表和外键约束。"""
    with engine.begin() as conn:
        # 检查是否有 user_id 列
        result = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='tasks' AND column_name='user_id'"
            )
        )
        has_user_id = result.fetchone() is not None

        if has_user_id:
            # 删除外键约束（如果存在）
            try:
                conn.execute(text("ALTER TABLE tasks DROP CONSTRAINT IF EXISTS tasks_user_id_fkey"))
            except Exception:
                pass
            # 重命名列
            conn.execute(text("ALTER TABLE tasks RENAME COLUMN user_id TO session_id"))

        # 删除 users 表
        conn.execute(text("DROP TABLE IF EXISTS users CASCADE"))

    # 确保新表结构正确
    Base.metadata.create_all(engine)
    print("迁移完成：user_id → session_id，users 表已移除")


if __name__ == "__main__":
    migrate()