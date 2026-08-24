"""图片保存与消息段处理。"""

import base64
import re
from hashlib import md5
from pathlib import Path

import httpx
from nonebot.log import logger

MAX_IMAGE_BYTES = 20 * 1024 * 1024

_EXT_BY_CONTENT_TYPE = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
}
_SAFE_EXTS = set(_EXT_BY_CONTENT_TYPE.values()) | {".jpeg", ".tiff", ".ico"}


def _ext_from_name(name: str) -> str | None:
    """从文件名或 URL 提取合法图片扩展名。"""
    clean = re.split(r"[?#]", name, maxsplit=1)[0]
    m = re.search(r"\.([A-Za-z0-9]+)$", clean)
    if not m:
        return None
    ext = "." + m.group(1).lower()
    return ext if ext in _SAFE_EXTS else None


def guess_ext(name: str, content_type: str | None) -> str:
    """按名称扩展名、content-type 顺序推断扩展名。"""
    ext = _ext_from_name(name)
    if ext:
        return ext
    if content_type:
        ct = content_type.split(";")[0].strip().lower()
        if ct in _EXT_BY_CONTENT_TYPE:
            return _EXT_BY_CONTENT_TYPE[ct]
    return ".png"


async def download_image(url: str) -> tuple[bytes, str] | None:
    """下载图片，返回 (内容, content-type)，失败或超限返回 None。"""
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.content
            if len(data) > MAX_IMAGE_BYTES:
                logger.warning(f"[AutoSpeak] 图片过大: {url}")
                return None
            return data, resp.headers.get("content-type", "")
    except Exception as e:
        logger.warning(f"[AutoSpeak] 图片下载失败: {url} ({e})")
        return None


def save_image_bytes(data: bytes, images_dir: Path, ext: str) -> str:
    """按内容 md5 命名保存，已存在跳过，返回文件名。"""
    name = md5(data).hexdigest() + ext
    path = images_dir / name
    if not path.exists():
        path.write_bytes(data)
    return name


async def save_image_segment(seg, images_dir: Path) -> str | None:
    """保存单个 image 消息段，返回文件名，失败返回 None。"""
    file = str(seg.data.get("file", ""))
    url = str(seg.data.get("url", ""))

    if file.startswith("base64://"):
        try:
            data = base64.b64decode(file[len("base64://"):])
            if len(data) > MAX_IMAGE_BYTES:
                return None
            return save_image_bytes(data, images_dir, guess_ext(file, None))
        except Exception as e:
            logger.warning(f"[AutoSpeak] base64 图片解码失败: {e}")
        return None

    local = None
    if file.startswith("file://"):
        p = file[len("file://"):]
        # file:///C:/path -> C:/path
        if len(p) >= 3 and p[0] == "/" and p[2] == ":":
            p = p[1:]
        local = Path(p)
    elif ":" in file or file.startswith(("/", "\\\\")):
        local = Path(file)
    if local is not None and local.is_file():
        try:
            ext = _ext_from_name(local.name) or ".png"
            return save_image_bytes(local.read_bytes(), images_dir, ext)
        except Exception as e:
            logger.warning(f"[AutoSpeak] 本地图片读取失败: {e}")
        return None

    if url:
        result = await download_image(url)
        if result:
            data, content_type = result
            return save_image_bytes(data, images_dir, guess_ext(url, content_type))
    return None
