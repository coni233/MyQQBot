from pathlib import Path

from nonebot import get_plugin_config
from pydantic import Field, BaseModel


class Config(BaseModel):
    """Scoped plugin configuration.

    Every field is prefixed so it is unambiguous in NoneBot's global config.
    """

    bili_data: Path | None = None
    bili_subscription_dynamic_interval: int = Field(default=120, ge=30)
    bili_subscription_live_interval: int = Field(default=30, ge=10)
    bili_subscription_request_timeout: float = Field(default=15.0, gt=0)
    bili_subscription_request_concurrency: int = Field(default=4, ge=1, le=20)
    bili_subscription_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) " "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
    )
    bili_subscription_web_enabled: bool = False
    bili_subscription_web_path: str = "/bili-subscription"
    bili_subscription_web_token: str = ""
    bili_subscription_web_public_url: str = ""
    bili_subscription_render_width: int = Field(default=720, ge=480, le=1600)
    bili_subscription_render_timeout: int = Field(default=15000, ge=3000, le=60000)
    bili_subscription_auto_install_browser: bool = True
    bili_subscription_initial_dynamic_limit: int = Field(default=3, ge=1, le=20)
    bili_subscription_enable_dynamic: bool = True
    bili_subscription_enable_live: bool = True


# get_plugin_config is intentionally called exactly once in this plugin.
plugin_config = get_plugin_config(Config)
