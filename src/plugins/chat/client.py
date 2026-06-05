import asyncio
from nonebot.log import logger
from openai import AsyncOpenAI
from src.plugins.chat.config import llm_model_config
from src.plugins.chat.verify import ResponseModel
from typing import Any


client = AsyncOpenAI(
    api_key=llm_model_config["api_key"],
    base_url=llm_model_config["base_url"],
)

async def init_model_config() -> dict[str, Any]:
    model_config = {
        "model": llm_model_config["model_name"],
        "max_tokens": llm_model_config["max_tokens"]
    }

    if llm_model_config.get("provider", "") == "gemini":
        model_config.update({
            "reasoning_effort": llm_model_config["reasoning_effort"],
            "temperature": llm_model_config["temperature"]
        })
    else:
        if llm_model_config["thinking"] == "enabled":
            model_config.update({
                "reasoning_effort": llm_model_config["reasoning_effort"],
                "extra_body": {
                    "thinking": {"type": "enabled"}
                }
            })
        elif llm_model_config["thinking"] == "disabled":
            model_config.update({
                "temperature": llm_model_config["temperature"]
            })
        else:
            raise ValueError("Unknown thinking type")

    return model_config

async def require_llm(message: list[dict]) -> str:
    model_config = await init_model_config()
    response = await client.chat.completions.create(    # type: ignore
        messages=message,
        response_format={"type": "json_object"},
        stream=False,
        **model_config
    )
    return response.choices[0].message.content

async def general_chat(message: list[dict]) -> ResponseModel:
    for i in range(llm_model_config["retry_times"] + 1):
        try:
            response = await asyncio.wait_for(
                require_llm(message),
                timeout=llm_model_config["timeout"]
            )
            response = ResponseModel.model_validate_json(response)
            return response

        except Exception as e:
            if i < llm_model_config["retry_times"]:
                logger.error(f"request llm api failed: [{e}], retrying {i + 1} times")

    raise Exception("request llm api failed completely")