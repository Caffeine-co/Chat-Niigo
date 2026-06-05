import aiofiles
import time
from src.plugins.chat.config import preset_config, llm_model_config
from src.plugins.chat.utils import uid_to_tag, ts_to_time, local_img_to_base64


async def init_system_input() -> str:
    async with aiofiles.open(preset_config["prompt_file"], 'r', encoding='utf-8') as file:
        content = await file.read()
    return content

async def init_user_input(self_id: int, msg_list: list[dict], user_list: list[dict], group_name: str) -> list[dict]:
    self_info = [
        "# 系统与自我信息",
        f"- ID：{self_id}",
        f"- 昵称：{preset_config['name']}",
        f"- 当前时间：{await ts_to_time(int(time.time()))}",
        f"- 群名称：{group_name}",
    ]
    self_info = "\n".join(self_info)

    user_info = ["# 用户信息"]
    for user in user_list:
        if user["uid"] == self_id:
            continue

        user_info.append(f"- {uid_to_tag(user['uid'])}(ID：{user['uid']}，昵称：{user['nickname']})")

        if not user["memory"]:
            user_info.append(f"  - 暂无记忆")

        for i, memory in enumerate(user["memory"]):
            user_info.append(f"  - 记忆 {i + 1}：{memory}")

    user_info = "\n".join(user_info)

    content_list = [
        {
            "type": "text",
            "text": "\n".join([self_info, user_info])
        },
        {
            "type": "text",
            "text": "# 群聊消息"
        }

    ]

    # todo: pjsk_knowledge_base

    for msg in msg_list:
        if msg["nickname"] == "self" or msg["uid"] == self_id:
            content_list.append({
                "type": "text",
                "text": f"[{await ts_to_time(msg['time'])}]<{msg['mid']}>我：{msg['content']}"
            })
        else:
            content_list.append({
                "type": "text",
                "text": f"[{await ts_to_time(msg['time'])}]<msg_id:{msg['mid']}>{uid_to_tag(msg['uid'])}：{msg['content']}"
            })

        if llm_model_config["enable_img_multimode"] and msg["img_data"]:
            for img in msg["img_data"]:
                img_b64 = await local_img_to_base64(img, need_b64_mark=False)
                content_list.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{img_b64}"
                    },
                })

    return content_list