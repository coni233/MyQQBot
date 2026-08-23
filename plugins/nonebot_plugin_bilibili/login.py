from __future__ import annotations

import io
import time
import asyncio
from typing import Any

import qrcode

from .api import bilibili_api
from .database import repository


def make_qr_png(url: str) -> bytes:
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    image: Any = qr.make_image(fill_color="black", back_color="white")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


async def wait_for_login(key: str, timeout: int = 180) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        code, message, cookie = await bilibili_api.poll_qr_login(key)
        if code == 0 and cookie:
            await repository.set_setting("bilibili_cookie", cookie)
            return cookie
        if code == 86038:
            raise TimeoutError("二维码已失效")
        if code not in {86101, 86090}:
            raise RuntimeError(message or f"扫码登录失败：{code}")
        await asyncio.sleep(2)
    raise TimeoutError("等待扫码超时")


def mask_cookie(cookie: str) -> str:
    if not cookie:
        return "未配置"
    names = [item.split("=", 1)[0].strip() for item in cookie.split(";") if "=" in item]
    return "已配置：" + ", ".join(names)
