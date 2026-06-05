import json
import sys
import nonebot
from nonebot.adapters.onebot.v11.adapter import Adapter as ONEBOT_V11Adapter
from nonebot.log import logger, default_filter
from nonebot.plugin import _managers
from nonebot.plugin.manager import PluginManager
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from typing import Any


def logo_startup(version: str, environment: str) -> None:
    console = Console()
    console.clear()
    logo = r"""
      ___                                   ___           ___      
     /\__\          ___         ___        /\  \         /\  \     
    /::|  |        /\  \       /\  \      /::\  \       /::\  \    
   /:|:|  |        \:\  \      \:\  \    /:/\:\  \     /:/\:\  \   
  /:/|:|  |__      /::\__\     /::\__\  /:/  \:\  \   /:/  \:\  \  
 /:/ |:| /\__\  __/:/\/__/  __/:/\/__/ /:/__/_\:\__\ /:/__/ \:\__\ 
 \/__|:|/:/  / /\/:/  /    /\/:/  /    \:\  /\ \/__/ \:\  \ /:/  / 
     |:/:/  /  \::/__/     \::/__/      \:\ \:\__\    \:\  /:/  /  
     |::/  /    \:\__\      \:\__\       \:\/:/  /     \:\/:/  /   
     /:/  /      \/__/       \/__/        \::/  /       \::/  /    
     \/__/                                 \/__/         \/__/     
    """
    logo_text = Text(logo, style="#884499")
    info_text = Text.assemble(
        ("\n>_ 25時、ナイトコードで。\n", "#884499"),
        (f">_ Version    : {version}\n", "#bb6688"),
        (f">_ Client Env : {environment}\n", "#8888cc"),
        (">_ Status     : Initializing...\n", "#ccaa88"),
        (">_ Powered by Nonebot2, Developed by Caffeine-co", "#ddaacc")
    )
    logo_text.append_text(info_text)
    panel = Panel(
        Align.center(logo_text),
        border_style="#ffffff",
        expand=False,
    )
    console.print(panel)
    console.print("\n")

def init_log() -> None:
    logger.remove()
    for custom_level in [
        {"name": "THINKING", "no": 25, "color": "<fg #bb6688><bg #884499>"},
        {"name": "WILLING", "no": 25, "color": "<fg #8888cc><bg #884499>"},
        {"name": "CHAT", "no": 25, "color": "<fg #ccaa88><bg #884499>"},
        {"name": "CHOOSE", "no": 25, "color": "<fg #ddaacc><bg #884499>"}
    ]:
        logger.level(**custom_level)
    custom_format: str = (
        "[<fg #39c5bb>{time:MM-DD HH:mm:ss}</fg #39c5bb>] "
        "[<fg #884499>ナイトコード</fg #884499>] "
        "| <lvl>{level}</lvl> | "
        "{message}"
    )
    logger.add(
        sys.stdout,
        level=0,
        diagnose=False,
        filter=default_filter,
        format=custom_format,
    )

def get_configs() -> dict[str, Any]:
    try:
        with open("configs.json", "r", encoding="utf-8") as f:
            configs: dict = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load configs: {e}")
        input("Press Enter to quit...")
        sys.exit(1)
    return configs

def import_chat_plugin() -> None:
    manager = PluginManager(["src.plugins.test"])
    _managers.append(manager)
    import src.plugins.chat


if __name__ == "__main__":
    ver, env = "vdev", "dev"

    init_log()
    logo_startup(ver, env)
    extra_configs = get_configs()

    nonebot.init(
        version=ver,
        environment=env,
        driver="~fastapi",
        localstore_use_cwd=True,
        command_start={"/"},
        command_sep={" "},
        **extra_configs
    )
    driver = nonebot.get_driver()
    driver.register_adapter(ONEBOT_V11Adapter)

    import_chat_plugin()

    nonebot.run()