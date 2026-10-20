import re
import os
import asyncio
import aiohttp

from pathlib import Path
from urllib.parse import urlparse
from typing import Dict, List, Optional
from ..config import CACHE_DIR, HTTP_PROXY

from nonebot import logger


class ImageManager:
    """图片管理器"""

    def __init__(self, cache_dir: Path = CACHE_DIR, proxy: str = HTTP_PROXY):
        self.cache_dir = cache_dir
        self.proxy = proxy

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        name = re.sub(r'\s+', '_', name)
        if len(name) > 100:
            name = name[:100]
        return name

    def get_cache_key(self, img_type: str, identifier: str, anime_name: str = None) -> str:
        safe_id = self._sanitize_filename(identifier)
        if img_type == "cover":
            return f"cover_{safe_id}"
        elif img_type == "character":
            if anime_name:
                return f"character_{safe_id}_{self._sanitize_filename(anime_name)}"
            return f"character_{safe_id}"
        elif img_type == "screenshot":
            return f"screenshot_{safe_id}"
        return f"{img_type}_{safe_id}"

    def get_cache_path(self, cache_key: str, img_url: str = None) -> Path:
        if img_url:
            parsed = urlparse(img_url)
            ext = os.path.splitext(parsed.path)[1]
            if not ext or len(ext) > 5:
                ext = '.jpg'
        else:
            ext = '.jpg'
        return self.cache_dir / f"{cache_key}{ext}"

    async def _download_one(self, img_url: str, filepath: Path) -> bool:
        """下载单张图片"""
        if not img_url:
            return False
        if img_url.startswith('//'):
            img_url = 'https:' + img_url

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
        }

        for attempt in range(3):
            try:
                async with aiohttp.ClientSession() as sess:
                    async with sess.get(img_url, headers=headers, proxy=self.proxy or None, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status != 200:
                            if attempt < 2:
                                await asyncio.sleep(1)
                                continue
                            logger.warning(f"图片下载 HTTP {resp.status}（重试耗尽）: {img_url}")
                            return False

                        content = await resp.read()
                        if len(content) < 1000:
                            if attempt < 2:
                                await asyncio.sleep(1)
                                continue
                            logger.warning(f"图片过小（重试耗尽）: {img_url}")
                            return False

                        with open(filepath, 'wb') as f:
                            f.write(content)
                        return True

            except asyncio.TimeoutError:
                pass
            except aiohttp.ClientConnectorError:
                pass
            except Exception:
                pass

            if attempt < 2:
                await asyncio.sleep(1)

        logger.warning(f"图片下载失败（3次重试）: {img_url}")
        return False

    async def download_image(self, img_url: str, img_type: str,
                             identifier: str, anime_name: str = None) -> Optional[str]:
        """下载图片并返回本地路径"""
        if not img_url:
            return None

        try:
            cache_key = self.get_cache_key(img_type, identifier, anime_name)
            cache_path = self.get_cache_path(cache_key, img_url)

            if cache_path.exists():
                return str(cache_path)

            logger.debug(f"下载图片 [{img_type}]: {img_url[:80]}...")
            success = await self._download_one(img_url, cache_path)
            return str(cache_path) if success else None

        except Exception as e:
            logger.opt(exception=True).error(f"图片下载异常 [{img_type}]")
            return None

    async def batch_download_images(self, tasks: List[tuple]) -> Dict[str, str]:
        """批量下载图片"""
        results = {}
        semaphore = asyncio.Semaphore(10)

        async def _task(task):
            async with semaphore:
                if len(task) == 4:
                    img_url, img_type, identifier, anime_name = task
                else:
                    img_url, img_type, identifier = task
                    anime_name = None

                cache_key = self.get_cache_key(img_type, identifier, anime_name)
                cache_path = self.get_cache_path(cache_key, img_url)
                if cache_path.exists():
                    results[cache_key] = str(cache_path)
                    return cache_key

                path = await self.download_image(img_url, img_type, identifier, anime_name)
                if path:
                    results[cache_key] = path
                return cache_key

        batch_size = 20
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            await asyncio.gather(*[_task(t) for t in batch])
            if i + batch_size < len(tasks):
                await asyncio.sleep(0.5)

        return results
