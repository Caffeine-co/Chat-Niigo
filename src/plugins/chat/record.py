import aiosqlite
import json
from nonebot.adapters.onebot.v11.event import GroupMessageEvent
from nonebot.adapters.onebot.v11.message import Message
from nonebot.adapters.onebot.v11.utils import unescape
from nonebot.log import logger
from src.plugins.chat.config import llm_model_config, group_chat_config
from src.plugins.chat.utils import download_image, delete_image, check_null_msg
from uuid import uuid5, NAMESPACE_OID


async def init_group_msg_db(gid: int, db: aiosqlite.Connection):
    await db.execute(f"""
        CREATE TABLE IF NOT EXISTS msg_{gid} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time INTEGER,
            mid INTEGER,
            uid INTEGER,
            nickname TEXT,
            content TEXT,
            img_data TEXT
        )
    """)

async def format_user_msg(message: Message) -> tuple[str,list]:
    content = ""
    img_urls = []
    for seg in message:
        if seg.type == "text":
            content += seg.data["text"]
        elif seg.type == "face":
            content += f"[CQ:face,id={seg.data.get('id')}]"
        elif seg.type == "image":
            if llm_model_config["enable_img_multimode"]:
                img_urls.append(seg.data.get("url"))
            if summary := seg.data.get("summary"):
                if summary == "[动画表情]":
                    content += "[CQ:image,summary=[动画表情]]"
                else:
                    content += f"[CQ:image,summary={summary}]"
            else:
                content += "[CQ:image]"
        elif seg.type == "record":
            content += "[CQ:record]"
        elif seg.type == "video":
            content += "[CQ:video]"
        elif seg.type == "at":
            content += f"[CQ:at,qq={seg.data.get('qq')}]"
        elif seg.type == "reply":
            content += f"[CQ:reply,id={seg.data.get('id')}]"
        elif seg.type == "forward":
            content += f"[CQ:forward,id={seg.data.get('id')}]"
        elif seg.type == "json":
            try:
                json_data = seg.data.get("data", "{}")
                json_str = unescape(json_data)
                json_dict = json.loads(json_str)
                app_val = json_dict.get("app", "unknown")
                prompt_val = json_dict.get("prompt", "")
                content += f'[CQ:json,data={{"app":"{app_val}","prompt":"{prompt_val}"}}]'
            except Exception:
                content += "[CQ:json,data=error]"
        elif seg.type == "file":
            content += f"[CQ:file,file={seg.data.get('file')}]"
        else:
            content += f"[CQ:{seg.type}]"
    return content, img_urls

async def record_group_user_msg(event: GroupMessageEvent) -> None:
    if await check_null_msg(event.original_message):
        return

    content, img_urls = await format_user_msg(message=event.original_message)

    local_img_ids = []
    if llm_model_config["enable_img_multimode"] and img_urls:
        for i, img_url in enumerate(img_urls):
            img_id = str(uuid5(NAMESPACE_OID, f"{event.time}_{event.group_id}_{event.user_id}_{i}"))
            try:
                await download_image(img_url, img_id)
            except Exception as e:
                logger.error(f"download message_{event.message_id}'s image_{i + 1} error: {e}")
            else:
                local_img_ids.append(img_id)

    img_data = json.dumps(local_img_ids, ensure_ascii=False)

    async with aiosqlite.connect(group_chat_config["msg_db"]) as db:
        await init_group_msg_db(event.group_id, db)
        nickname = event.sender.card or event.sender.nickname or "null"
        await db.execute(f"""
            INSERT INTO msg_{event.group_id} (time, mid, uid, nickname, content, img_data )
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                event.time,
                event.message_id,
                event.user_id,
                nickname,
                content,
                img_data
            )
        )
        await db.commit()

async def record_group_self_msg(time: int, gid: int, mid: int, sid: int, content: str, nickname: str = "self") -> None:
    async with aiosqlite.connect(group_chat_config["msg_db"]) as db:
        await init_group_msg_db(gid, db)
        await db.execute(f"""
            INSERT INTO msg_{gid} (time, mid, uid, nickname, content, img_data )
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                time,
                mid,
                sid,
                nickname,
                content,
                "[]"
            )
        )
        await db.commit()

async def get_group_msg_list(gid: int) -> list[dict]:
    async with aiosqlite.connect(group_chat_config["msg_db"]) as db:
        db.row_factory = aiosqlite.Row
        try:
            async with db.execute(f"SELECT * FROM msg_{gid} ORDER BY time ASC, id ASC") as cursor:
                rows = await cursor.fetchall()
                result = []
                for row in rows:
                    msg_data = dict(row)
                    msg_data["img_data"] = json.loads(msg_data["img_data"])
                    result.append(msg_data)
                return result
        except aiosqlite.OperationalError:
            return []

async def update_group_msg_list(gid: int) -> None:
    async with aiosqlite.connect(group_chat_config["msg_db"]) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(f"SELECT COUNT(*) FROM msg_{gid}")
        row_count = (await cursor.fetchone())[0]

        if row_count <= group_chat_config["max_msg_reserve_num"]:
            return

        cursor = await db.execute(f"""
            SELECT img_data FROM msg_{gid}
            ORDER BY time DESC
            LIMIT -1 OFFSET ?
        """,
            (group_chat_config["max_msg_reserve_num"],)
        )
        outdated_rows = await cursor.fetchall()

        for row in outdated_rows:
            img_data = json.loads(row["img_data"])
            for img in img_data:
                await delete_image(img)

        await db.execute(f"""
            CREATE TABLE IF NOT EXISTS msg_{gid}_temp (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time INTEGER,
                mid INTEGER,
                uid INTEGER,
                nickname TEXT,
                content TEXT,
                img_data TEXT
            )
        """)

        await db.execute(f"""
            INSERT INTO msg_{gid}_temp (time, mid, uid, nickname, content, img_data)
            SELECT time, mid, uid, nickname, content, img_data
            FROM (
                SELECT * FROM msg_{gid}
                ORDER BY time DESC
                LIMIT ?
            )
            ORDER BY time ASC, id ASC
        """,
            (group_chat_config["max_msg_reserve_num"],)
        )

        await db.execute(f"DROP TABLE msg_{gid}")
        await db.execute(f"ALTER TABLE msg_{gid}_temp RENAME TO msg_{gid}")
        await db.commit()

async def delete_group_msg_table(gid: int) -> None:
    async with aiosqlite.connect(group_chat_config["msg_db"]) as db:
        db.row_factory = aiosqlite.Row
        try:
            cursor = await db.execute(f"SELECT img_data FROM msg_{gid}")
            all_rows = await cursor.fetchall()
            for row in all_rows:
                img_data = json.loads(row["img_data"])
                for img in img_data:
                    await delete_image(img)

            await db.execute(f"DROP TABLE msg_{gid}")
            await db.commit()
        except aiosqlite.OperationalError:
            pass