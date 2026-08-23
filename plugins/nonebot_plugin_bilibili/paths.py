from pathlib import Path

from nonebot_plugin_localstore import get_plugin_data_dir

from .config import plugin_config


def resolve_data_dir(configured: Path | None, localstore_dir: Path | None = None) -> Path:
    if configured is None:
        if localstore_dir is None:
            raise ValueError("localstore_dir is required when BILI_DATA is not configured")
        return localstore_dir
    path = configured.expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


DATA_DIR: Path = resolve_data_dir(
    plugin_config.bili_data,
    get_plugin_data_dir() if plugin_config.bili_data is None else None,
)
DATABASE_PATH = DATA_DIR / "subscription.sqlite3"
FONT_DIR = DATA_DIR / "fonts"
TEMPLATE_DIR = DATA_DIR / "templates"
RENDER_DIR = DATA_DIR / "renders"


def ensure_data_dirs() -> None:
    for path in (DATA_DIR, FONT_DIR, TEMPLATE_DIR, RENDER_DIR):
        path.mkdir(parents=True, exist_ok=True)


# Create a configured BILI_DATA tree before the database or web routes can use it.
ensure_data_dirs()
