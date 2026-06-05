from nonebot.adapters.onebot.v11.event import GroupMessageEvent as GroupMsgEvent
from src.plugins.chat.config import configs, group_chat_config


async def not_to_me(event: GroupMsgEvent) -> bool:
    return not event.is_tome()

async def enable_help() -> bool:
    return configs.enable_help

async def check_admin(event: GroupMsgEvent) -> bool:
    return event.user_id in configs.bot_admins

async def check_group_perm(event: GroupMsgEvent) -> bool:
    if group_chat_config["enable"]:
        run_mode = group_chat_config["run_mode"]
        if run_mode == "whitelist":
            return event.group_id in group_chat_config[f"whitelists"]
        else:
            return event.group_id not in group_chat_config["blacklists"]
    else:
        return False

async def check_user_blacklist(event: GroupMsgEvent) -> bool:
    return event.user_id not in configs.user_blacklists