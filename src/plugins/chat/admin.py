from src.plugins.chat.config import configs, group_chat_config
from src.plugins.chat.exception import ModeAlreadySetError, AlreadyExistError, DoesNotExistError
from src.plugins.chat.utils import read_json, write_json


async def check_group_mode(mode: str) -> bool:
    return mode == group_chat_config["run_mode"]

async def change_group_run_mode(new_mode: str) -> None:
    if await check_group_mode(mode=new_mode):
        raise ModeAlreadySetError
    group_chat_config["run_mode"] = new_mode
    raw_config = await read_json("configs.json")
    raw_config["group_chat_config"]["run_mode"] = new_mode
    await write_json("configs.json", raw_config)

async def add_group_list(gid: int, mode: str) -> None:
    if gid in group_chat_config[f"{mode}s"]:
        raise AlreadyExistError
    group_chat_config[f"{mode}s"].append(gid)
    raw_config = await read_json("configs.json")
    raw_config["group_chat_config"][f"{mode}s"].append(gid)
    await write_json("configs.json", raw_config)

async def remove_group_list(gid: int, mode: str) -> None:
    if gid not in group_chat_config[f"{mode}s"]:
        raise DoesNotExistError
    group_chat_config[f"{mode}s"].remove(gid)
    raw_config = await read_json("configs.json")
    raw_config["group_chat_config"][f"{mode}s"].remove(gid)
    await write_json("configs.json", raw_config)

async def add_user_blacklist(uid: int) -> None:
    if uid in configs.user_blacklists:
        raise AlreadyExistError
    configs.user_blacklists.add(uid)
    raw_config = await read_json("configs.json")
    raw_config["user_blacklists"].add(uid)
    await write_json("configs.json", raw_config)

async def remove_user_blacklist(uid: int) -> None:
    if uid not in configs.user_blacklists:
        raise DoesNotExistError
    configs.user_blacklists.remove(uid)
    raw_config = await read_json("configs.json")
    raw_config["user_blacklists"].remove(uid)
    await write_json("configs.json", raw_config)