import aiofiles
import base64
import httpx
import json
import os
from datetime import datetime, timezone, timedelta
from nonebot.adapters.onebot.v11.message import Message, MessageSegment
from pathlib import Path
from src.plugins.chat.config import preset_config, llm_model_config
from typing import Any

def uid_to_tag(uid: int) -> str:
    base62_alphabet = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if uid == 0:
        return base62_alphabet[0]

    base62_list = []
    while uid > 0:
        uid, rem = divmod(uid, 62)
        base62_list.append(base62_alphabet[rem])

    return "".join(reversed(base62_list))

async def download_image(url: str, img_name: str) -> None:
    Path(llm_model_config["temp_img_dir"]).mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        async with aiofiles.open(f"{llm_model_config['temp_img_dir']}/{img_name}", 'wb') as file:
            async for chunk in response.aiter_bytes(chunk_size=1024):
                await file.write(chunk)

async def delete_image(img_name: str) -> None:
    try:
        os.remove(f"{llm_model_config['temp_img_dir']}/{img_name}")  # 物理抹除本地图片
    except FileNotFoundError:
        pass

async def local_img_to_base64(img_name: str, need_b64_mark: bool) -> str:
    async with aiofiles.open(f"{llm_model_config['temp_img_dir']}/{img_name}", "rb") as f:
        data = await f.read()
        img = base64.b64encode(data).decode("utf-8")   # utf-8/ascii
    if need_b64_mark:
        return f"base64://{img}"
    else:
        return img

async def ts_to_time(ts: int) -> str:
    tz = timezone(timedelta(hours=preset_config["tz_offset"]))
    dt = datetime.fromtimestamp(ts, tz=tz)
    return dt.isoformat()

async def time_to_ts(dt_str: str) -> int:
    dt = datetime.fromisoformat(dt_str)
    return int(dt.timestamp())

async def add_space_after_at(msg: Message) -> Message:
    for i, d in reversed(list(enumerate(msg))):
        if d.type == "at":
            msg.insert(i + 1, MessageSegment.text(" "))
    return msg

async def check_null_msg(msg: Message) -> bool:
    null_text_num = sum(1 for seg in msg if seg.type == "text" and seg.data["text"] == "")
    seg_length = len(msg)
    return null_text_num == seg_length

async def read_json(path: str | Path) -> Any:
    """
    读取 json 文件
    :param path: 文件地址
    :return: 已解析的数据内容
    """
    async with aiofiles.open(path, 'r', encoding='utf-8') as f:
        content = await f.read()
    return json.loads(content)

async def write_json(path: str | Path, content: Any) -> None:
    """
    写入 json 文件，路径不存在自动创建
    :param path: 文件地址
    :param content: 数据内容
    :return: None
    """
    # if not isinstance(path, Path):
    path = Path(path)
    path.parent.resolve().mkdir(parents=True, exist_ok=True)

    async with aiofiles.open(path, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(content, ensure_ascii=False, indent=2))