import aiosqlite
import json
from src.plugins.chat.config import group_chat_config


async def init_user_memory_db(gid: int, db: aiosqlite.Connection):
    await db.execute(f"""
        CREATE TABLE IF NOT EXISTS memory_{gid} (
            uid INTEGER PRIMARY KEY,
            memory TEXT NOT NULL
        )
    """)

async def save_user_memory(gid:int, uid: int, memory: list[str]) -> None:
    memory = json.dumps(memory, ensure_ascii=False)
    async with aiosqlite.connect(group_chat_config["memory_db"]) as db:
        await init_user_memory_db(gid, db)
        await db.execute(f"""
            INSERT INTO memory_{gid} (uid, memory) 
            VALUES (?, ?)
            ON CONFLICT(uid) DO UPDATE SET 
                memory = excluded.memory
        """, (uid, memory))
        await db.commit()

async def get_user_memory(gid: int, uid: int) -> list[str]:
    async with aiosqlite.connect(group_chat_config["memory_db"]) as db:
        db.row_factory = aiosqlite.Row
        await init_user_memory_db(gid, db)
        async with db.execute(f"""
            SELECT memory FROM memory_{gid} 
            WHERE uid = ?
        """, (uid,)) as cursor:
            row = await cursor.fetchone()
            return json.loads(row["memory"]) if row else []

async def delete_group_memory_table(gid: int) -> None:
    async with aiosqlite.connect(group_chat_config["memory_db"]) as db:
        await db.execute(f"DROP TABLE IF EXISTS memory_{gid}")
        await db.commit()

async def _delete_user_memory(gid: int, uid: int) -> None:
    async with aiosqlite.connect(group_chat_config["memory_db"]) as db:
        await init_user_memory_db(gid, db)
        await db.execute(f"DELETE FROM memory_{gid} WHERE uid = ?", (uid,))
        await db.commit()