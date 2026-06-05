from pydantic import BaseModel, model_validator, Field
from typing import Optional, Literal, Annotated, Union


class MemoryModel(BaseModel):
    user_id: int
    new_memory: list[str]

class TextData(BaseModel):
    text: str
class AtData(BaseModel):
    qq: int | Literal["all"]
class ReplyData(BaseModel):
    id: int

class TextSegment(BaseModel):
    type: Literal["text"]
    data: TextData
class AtSegment(BaseModel):
    type: Literal["at"]
    data: AtData
class ReplySegment(BaseModel):
    type: Literal["reply"]
    data: ReplyData

SegmentModel = Annotated[
    Union[TextSegment, AtSegment, ReplySegment],
    Field(discriminator="type")
]

MessageModel = list[SegmentModel]

class ResponseModel(BaseModel):
    thought: str = None
    enable_send_msg: bool
    message: Optional[list[MessageModel]] = None
    memory_update: list[MemoryModel]

    @model_validator(mode='after')
    def check_integrity(self) -> "ResponseModel":
        if self.enable_send_msg and not self.message:
            raise ValueError("enable_send_msg is true but message is missing")

        for idx, msg in enumerate(self.message):
            reply_count = sum(1 for seg in msg if seg.type == 'reply')
            total_segments = len(msg)

            if reply_count > 1:
                raise ValueError(f"message[{idx}] has {reply_count} reply segment, more than 1")

            if reply_count == 1 and total_segments == 1:
                raise ValueError(f"message[{idx}] only has 1 reply segments without others")

        return self