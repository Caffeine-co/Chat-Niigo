import asyncio
import random
from nonebot.adapters.onebot.v11.event import GroupMessageEvent
from src.plugins.chat.config import preset_config

will_config = preset_config["will_config"]

class Will:
    def __init__(self, group_id: int):
        self.group_id: int = group_id
        self.last_receive_time: int = 0
        self.current_receive_time: int = 0
        self.current_will: float = 0.0
        self.lock = asyncio.Lock()

    @property
    def enable_request(self) -> bool:
        return self.current_will >= will_config["limit"]

    async def _increase_general_message(self, event: GroupMessageEvent) -> None:
        async with self.lock:
            if self.current_receive_time == 0:
                self.last_receive_time = event.time
                self.current_receive_time = event.time
                self.current_will += 5.0

            self.last_receive_time = self.current_receive_time
            self.current_receive_time = event.time

            time_diff = self.current_receive_time - self.last_receive_time
            if time_diff < 5:
                diff_coef = 0.5
            elif 5 <= time_diff <= 10:
                diff_coef = 1.8
            elif 10 < time_diff <= 60:
                diff_coef = 1.0
            elif 60 < time_diff <= 600:
                diff_coef = 0.7
            elif 600 < time_diff <= 1800:
                diff_coef = 0.5
            else:
                diff_coef = 1.2

            adjusted_time = self.current_receive_time + (preset_config["tz_offset"] * 3600)
            hour = (adjusted_time % 86400) // 3600
            time_coefficient = will_config["time_coefficient"]
            if 1 <= hour < 4:
                time_coef = time_coefficient["wee_hours"]
            elif 4 <= hour < 7:
                time_coef = time_coefficient["matinal"]
            elif 7 <= hour < 10:
                time_coef = time_coefficient["morning"]
            elif 10 <= hour < 13:
                time_coef = time_coefficient["midday"]
            elif 13 <= hour < 16:
                time_coef = time_coefficient["afternoon"]
            elif 16 <= hour < 19:
                time_coef = time_coefficient["twilight"]
            elif 19 <= hour < 23:
                time_coef = time_coefficient["evening"]
            else:
                time_coef = time_coefficient["midnight"]

            random_coef = random.uniform(0.8, 1.2)

            final_increase = will_config["base_per_msg"] * diff_coef * time_coef * random_coef

            self.current_will = round(self.current_will + final_increase, 1)

    async def _increase_extra_segment(self, event: GroupMessageEvent) -> None:
        async with self.lock:
            for seg in event.original_message:
                if seg.type == "at" and seg.data.get("qq") == str(event.self_id):
                    self.current_will = round(self.current_will + will_config["increase_per_at"], 1)
                    return

            if event.reply and event.reply.sender.user_id == event.self_id:
                self.current_will = round(self.current_will + will_config["increase_per_reply"], 1)

    async def increase_on_receive(self, event: GroupMessageEvent) -> float:
        await self._increase_general_message(event)
        await self._increase_extra_segment(event)
        return self.current_will

    async def decrease_after_send(self) -> float:
        async with self.lock:
            self.current_will = round(self.current_will - will_config["decrease_after_send"], 1)
            return self.current_will

    async def reset_will(self) -> None:
        async with self.lock:
            self.current_will = 0.0

group_will: dict[int, Will] = {}

async def get_group_will(event: GroupMessageEvent) -> Will:
    if event.group_id not in group_will:
        group_will[event.group_id] = Will(event.group_id)

    return group_will[event.group_id]