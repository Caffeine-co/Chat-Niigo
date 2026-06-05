import asyncio
import time
from collections import defaultdict
from nonebot.adapters.onebot.v11.bot import Bot
from nonebot.adapters.onebot.v11.event import GroupMessageEvent as GMsgEvent
from nonebot.adapters.onebot.v11.message import Message as Msg, MessageSegment as MsgSeg
from nonebot.exception import MatcherException
from nonebot.internal.params import Depends
from nonebot.internal.rule import Rule
from nonebot.log import logger
from nonebot.plugin.on import on_message, on_command
from nonebot.plugin.on import CommandGroup as CmdGroup
from nonebot.params import CommandArg as CmdArg, Command as Cmd
from src.plugins.chat.admin import change_group_run_mode, check_group_mode,add_group_list, remove_group_list, add_user_blacklist, remove_user_blacklist
from src.plugins.chat.client import general_chat
from src.plugins.chat.config import configs, preset_config
from src.plugins.chat.exception import ModeAlreadySetError, AlreadyExistError, DoesNotExistError
from src.plugins.chat.memory import get_user_memory, save_user_memory, delete_group_memory_table
from src.plugins.chat.prompt import init_system_input, init_user_input
from src.plugins.chat.record import record_group_user_msg, get_group_msg_list, record_group_self_msg, update_group_msg_list, delete_group_msg_table
from src.plugins.chat.rule import check_group_perm, check_admin, check_user_blacklist, enable_help, not_to_me
from src.plugins.chat.status import Will, get_group_will
from src.plugins.chat.utils import add_space_after_at


conversation_locks = defaultdict(asyncio.Lock)

help_cmd = on_command("help", block=True, priority=1, rule=Rule(enable_help, not_to_me))
group_chat = on_message(block=True, priority=4, rule=Rule(check_group_perm, check_user_blacklist))
view_group_memory = on_command("memory", block=True, priority=1, rule=check_group_perm)
niigo_cmd = CmdGroup("niigo", block=True, priority=1, rule=not_to_me, prefix_aliases=True)
info_cmd = niigo_cmd.command("info")
admin_group_cmd = niigo_cmd.command(
    ("group", "chat"),
    aliases={
        ("group", "mode"),
        ("group", "whitelist"),
        ("group", "blacklist"),
        ("group", "wl"),
        ("group", "bl")
    },
    rule=check_admin
)

@help_cmd.handle()
async def help_cmd_(_: GMsgEvent, args: Msg = CmdArg()):
    if args:
        await help_cmd.finish()
    help_content = configs.help_content if configs.help_content else "example help content"
    await help_cmd.finish(help_content)

@group_chat.handle()
async def group_chat_(bot: Bot, event: GMsgEvent, will: Will = Depends(get_group_will)):
    async with conversation_locks[event.group_id]:
        await record_group_user_msg(event=event)

        will_before_receive = will.current_will
        will_after_receive = await will.increase_on_receive(event=event)
        logger.log("WILLING", f"[{event.group_id}] {will_before_receive} -> {will_after_receive}")

        if not will.enable_request:
            await group_chat.finish()

        msg_list = await get_group_msg_list(event.group_id)
        user_list = []
        for msg in msg_list:
            user_list.append({
                "uid": msg["uid"],
                "nickname": msg["nickname"]
            })
        user_list = list({user["uid"]: user for user in user_list}.values())

        for user in user_list:
            user_memory = await get_user_memory(event.group_id, user["uid"])
            user["memory"] = user_memory

        system_input = await init_system_input()
        user_input = await init_user_input(event.self_id, msg_list, user_list, event.group_name or "")
        message = [
            {"role": "system", "content": system_input},
            {"role": "user", "content": user_input}
        ]

        try:
            response = await general_chat(message)

        except Exception as e:
            logger.error(f"running chat error: {e}")

        else:
            logger.log("THINKING",f"[{event.group_id}] {response.thought}")
            if response.enable_send_msg:
                logger.log("CHOOSE", f"[{event.group_id}] send message : {response.enable_send_msg}")
                for msg in response.message:
                    msg = Msg([MsgSeg(**seg.model_dump()) for seg in msg])
                    send_msg = await add_space_after_at(msg)
                    raw_msg = str(send_msg)

                    text = "".join(seg.data["text"] for seg in send_msg if seg.type == "text")
                    await asyncio.sleep(len(text)/4)

                    send_data = await bot.send_group_msg(group_id=event.group_id, message=send_msg)
                    await record_group_self_msg(
                        int(time.time()),
                        event.group_id,
                        send_data["message_id"],
                        event.self_id,
                        raw_msg
                    )
                    logger.log("CHAT", f"[{event.group_id}] {raw_msg}")

            for new_memory in response.memory_update:
                await save_user_memory(event.group_id, new_memory.user_id, new_memory.new_memory)

            await update_group_msg_list(event.group_id)

        will_after_send = await will.decrease_after_send()
        logger.log("WILLING", f"[{event.group_id}] {will_after_receive} -> {will_after_send}")

@view_group_memory.handle()
async def view_group_memory_(bot: Bot, event: GMsgEvent, args: Msg = CmdArg()):
    uid = event.user_id
    arg_list = args.extract_plain_text().strip().split()
    try:
        if len(args) == 0:
            pass
        elif len(arg_list) == 1 and len(args) == 1 and arg_list[0].lstrip('+-').isdigit():
            uid = int(arg_list[0])
        else:
            raise
    except:
        await view_group_memory.finish()

    msg_list = [{
        "type": "node",
        "data": {
            "user_id": event.self_id,
            "nickname": preset_config["name"],
            "content": [
                {"type": "text", "data": {"text": f"ID：{uid}"}}
            ]
        }
    }]

    user_memory = await get_user_memory(event.group_id, uid)
    if user_memory:
        for um in user_memory:
            msg_list.append({
                "type": "node",
                "data": {
                    "user_id": event.self_id,
                    "nickname": preset_config["name"],
                    "content": [
                        {"type": "text", "data": {"text": f"- {um}"}}
                    ]
                }
            })
    else:
        msg_list.append({
            "type": "node",
            "data": {
                "user_id": event.self_id,
                "nickname": preset_config["name"],
                "content": [
                    {"type": "text", "data": {"text": "- 暂无"}}
                ]
            }
        })

    await bot.send_group_forward_msg(group_id=event.group_id, message=msg_list)

@info_cmd.handle()
async def info_cmd_(_: GMsgEvent, args: Msg = CmdArg()):
    if args:
        await info_cmd.finish()
    info_content = (
        "==== Niigo Chat ===="
        f"\n◆ Niigo Client {configs.version}"
        f"\n◆ Preset {preset_config.get('name', 'unknown')}"
    )
    await info_cmd.finish(info_content)

@admin_group_cmd.handle()
async def admin_group_cmd_(event: GMsgEvent, cmd: tuple[str, ...] = Cmd(), args: Msg = CmdArg(), will: Will = Depends(get_group_will)):
    if not args:
        await admin_group_cmd.finish()
    arg_list = args.extract_plain_text().strip().split()
    if len(arg_list) not in [1, 2]:
        await admin_group_cmd.finish()

    match cmd[2]:
        case "chat":
            if len(arg_list) != 1:
                await admin_group_cmd.finish()
            match arg_list[0]:
                case "clear" | "reset":
                    try:
                        await delete_group_memory_table(event.group_id)
                        await delete_group_msg_table(event.group_id)
                        await will.reset_will()
                        logger.log("WILLING", f"[{event.group_id}] reset success")
                        await admin_group_cmd.finish("group chat reset success")
                    except MatcherException:
                        pass
                    except Exception as e:
                        logger.error(f"group chat reset error: {e}")
                        await admin_group_cmd.finish(f"group chat reset error")
        case "mode":
            if len(arg_list) != 2:
                await admin_group_cmd.finish()
            match (arg_list[0], arg_list[1]):
                case ("set", "whitelist" | "wl"):
                    try:
                        await change_group_run_mode("whitelist")
                        await admin_group_cmd.finish(f"set group chat run mode success")
                    except MatcherException:
                        pass
                    except ModeAlreadySetError:
                        await admin_group_cmd.finish(f"mode whitelist already set")
                    except Exception as e:
                        logger.error(f"set group chat run mode error: {e}")
                        await admin_group_cmd.finish(f"set group chat run mode error")
                case ("set", "blacklist" | "bl"):
                    try:
                        await change_group_run_mode("blacklist")
                        await admin_group_cmd.finish(f"set group chat run mode success")
                    except MatcherException:
                        pass
                    except ModeAlreadySetError:
                        await admin_group_cmd.finish(f"mode blacklist already set")
                    except Exception as e:
                        logger.error(f"set group chat run mode error: {e}")
                        await admin_group_cmd.finish(f"set group chat run mode error")
        case "whitelist" | "wl":
            if len(arg_list) == 1:
                gid = event.group_id
                try:
                    match arg_list[0]:
                        case "set":
                            await add_group_list(gid, "whitelist")
                            await admin_group_cmd.finish(f"set whitelist success")
                        case"unset":
                            await remove_group_list(gid, "whitelist")
                            await admin_group_cmd.finish(f"unset whitelist success")
                except MatcherException:
                    pass
                except AlreadyExistError:
                    await admin_group_cmd.finish(f"group already exist in whitelist")
                except DoesNotExistError:
                    await admin_group_cmd.finish(f"group does not exist in whitelist")
                except Exception as e:
                    logger.error(f"change group whitelist error: {e}")
                    await admin_group_cmd.finish(f"change group whitelist error")
            elif len(arg_list) == 2 and arg_list[1].lstrip('+-').isdigit():
                gid = int(arg_list[1])
                try:
                    match arg_list[0]:
                        case "add":
                            await add_group_list(gid, "whitelist")
                            await admin_group_cmd.finish(f"add whitelist success")
                        case "remove" | "rm":
                            await remove_group_list(gid, "whitelist")
                            await admin_group_cmd.finish(f"remove whitelist success")
                except MatcherException:
                    pass
                except AlreadyExistError:
                    await admin_group_cmd.finish(f"group already exist in whitelist")
                except DoesNotExistError:
                    await admin_group_cmd.finish(f"group does not exist in whitelist")
                except Exception as e:
                    logger.error(f"change group whitelist error: {e}")
                    await admin_group_cmd.finish(f"change group whitelist error")
        case "blacklist" | "bl":
            if len(arg_list) == 1:
                gid = event.group_id
                try:
                    match arg_list[0]:
                        case "set":
                            await add_group_list(gid, "blacklist")
                            await admin_group_cmd.finish(f"set blacklist success")
                        case"unset":
                            await remove_group_list(gid, "blacklist")
                            await admin_group_cmd.finish(f"unset blacklist success")
                except MatcherException:
                    pass
                except AlreadyExistError:
                    await admin_group_cmd.finish(f"group already exist in blacklist")
                except DoesNotExistError:
                    await admin_group_cmd.finish(f"group does not exist in blacklist")
                except Exception as e:
                    logger.error(f"change group blacklist error: {e}")
                    await admin_group_cmd.finish(f"change group blacklist error")
            elif len(arg_list) == 2 and arg_list[1].lstrip('+-').isdigit():
                gid = int(arg_list[1])
                try:
                    match arg_list[0]:
                        case "add":
                            await add_group_list(gid, "blacklist")
                            await admin_group_cmd.finish(f"add blacklist success")
                        case "remove" | "rm":
                            await remove_group_list(gid, "blacklist")
                            await admin_group_cmd.finish(f"remove blacklist success")
                except MatcherException:
                    pass
                except AlreadyExistError:
                    await admin_group_cmd.finish(f"group already exist in blacklist")
                except DoesNotExistError:
                    await admin_group_cmd.finish(f"group does not exist in blacklist")
                except Exception as e:
                    logger.error(f"change group blacklist error: {e}")
                    await admin_group_cmd.finish(f"change group blacklist error")