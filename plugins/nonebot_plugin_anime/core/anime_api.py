import asyncio
import random
import aiohttp
from typing import Dict, Optional

from nonebot import logger

from ..config import BANGUMI_API_TOKEN, BANGUMI_API_UA, HTTP_PROXY, STAFF_ROLE_MAPPING, QUARTER_MONTHS, SUBJECT_TYPE_LABEL



class BangumiAPIClient:
    """Bangumi API"""

    def __init__(self, proxy: str = HTTP_PROXY):
        self._base = "https://api.bgm.tv"
        self._token = BANGUMI_API_TOKEN
        self._ua = BANGUMI_API_UA
        self._proxy = proxy
        self._max_retries = 3

    def _headers(self) -> dict:
        h = {
            "User-Agent": self._ua,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    async def _request(self, method: str, path: str, *, params: dict = None, json_body: dict = None) -> Optional[dict]:
        url = f"{self._base}{path}"
        for attempt in range(self._max_retries):
            try:
                async with aiohttp.ClientSession() as sess:
                    async with sess.request(
                        method, url,
                        headers=self._headers(),
                        params=params,
                        json=json_body,
                        proxy=self._proxy or None,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as resp:
                        if resp.status == 200:
                            return await resp.json()
                        elif resp.status == 429:
                            wait = (attempt + 1) * 10
                            logger.warning(f"Bangumi API 请求过多，等待 {wait}s")
                            await asyncio.sleep(wait)
                        else:
                            text = await resp.text()
                            logger.warning(f"Bangumi API HTTP {resp.status}: {text[:200]}")
            except aiohttp.ClientConnectorError as e:
                logger.warning(f"Bangumi API 连接错误 ({attempt + 1}/{self._max_retries}): {e}")
            except asyncio.TimeoutError:
                logger.warning(f"Bangumi API 超时 ({attempt + 1}/{self._max_retries})")
            except Exception as e:
                logger.opt(exception=True).error(f"Bangumi API 异常 ({attempt + 1}/{self._max_retries})")

            if attempt < self._max_retries - 1:
                delay = 2 * (2 ** attempt) + random.uniform(0, 1)
                await asyncio.sleep(delay)

        logger.error(f"Bangumi API 所有重试均失败: {method} {path}")
        return None

    async def _get(self, path: str, **params) -> Optional[dict]:
        return await self._request("GET", path, params=params or None)

    async def _post(self, path: str, body: dict, **params) -> Optional[dict]:
        return await self._request("POST", path, params=params or None, json_body=body)

    # ---------- 条目 ----------

    async def get_subject(self, subject_id: int) -> Optional[dict]:
        """获取条目详情  GET /v0/subjects/{id}"""
        return await self._get(f"/v0/subjects/{subject_id}")

    async def get_subject_persons(self, subject_id: int) -> Optional[list]:
        """获取制作人员  GET /v0/subjects/{id}/persons"""
        return await self._get(f"/v0/subjects/{subject_id}/persons")

    async def get_subject_characters(self, subject_id: int) -> Optional[list]:
        """获取角色列表  GET /v0/subjects/{id}/characters"""
        return await self._get(f"/v0/subjects/{subject_id}/characters")

    async def get_episodes(self, subject_id: int, limit: int = 100) -> Optional[dict]:
        """获取章节列表  GET /v0/episodes"""
        return await self._get("/v0/episodes", subject_id=subject_id, limit=limit, offset=0)

    async def search_subjects(self, keyword: str, *, filters: dict = None, sort: str = "rank", limit: int = 100) -> Optional[dict]:
        """搜索条目  POST /v0/search/subjects"""
        body = {"keyword": keyword, "sort": sort, "filter": filters or {}}
        return await self._post("/v0/search/subjects", body, limit=limit, offset=0)

    async def browse_subjects(self, *, type_id: int = 2, cat: int, sort: str = "date",
                                year: int, month: int,
                                limit: int = 50, offset: int = 0) -> Optional[dict]:
        """浏览条目  GET /v0/subjects

        type_id: 条目类型，2=动画
        cat:      分类，1=TV, 2=OVA, 3=剧场版, 5=WEB
        sort:     排序，date/rank
        year:     年份
        month:    月份
        """
        return await self._get("/v0/subjects", type=type_id, cat=cat, sort=sort, year=year,
                               month=month, limit=limit, offset=offset)


    async def fetch_anime_by_id(self, subject_id: int) -> Optional[dict]:
        """通过 ID 获取番剧完整数据"""
        subject = await self.get_subject(subject_id)
        if not subject:
            return None

        # 非动画类型跳过
        if subject.get("type") != 2:
            logger.debug(f"条目 {subject_id} 类型非动画（{SUBJECT_TYPE_LABEL.get(subject['type'], '未知')}），跳过")
            return None

        persons = await self.get_subject_persons(subject_id) or []
        characters = await self.get_subject_characters(subject_id) or []

        # 补充角色译名（逐个调角色详情取 infobox 中的 简体中文名）
        characters = await self._enrich_characters(characters)

        return self._assemble_anime_data(subject, persons, characters)


    async def fetch_anime_by_month(self, year: int, month: int, media_type: str = "tv", max_concurrency: int = 1) -> Dict[str, dict]:
        """获取指定季度的番剧列表，返回 {str(条目id): 完整数据} 字典"""
        cat_map = {"tv": 1, "ova": 2, "movie": 3, "web": 5}
        cat = cat_map.get(media_type)

        # 计算该季度包含的三个月
        q_start = month
        q_months = [q_start, q_start + 1, q_start + 2]

        logger.info(f"开始获取 {year}年{month}季度 {media_type} 番剧（逐月: {q_months}）")

        # 并发获取三个月的结果
        async def _browse_one(m: int) -> list:
            result = await self.browse_subjects(type_id=2, cat=cat, sort="date",
                                                 year=year, month=m,
                                                 limit=100, offset=0)
            return result["data"] if result and "data" in result else []

        monthly_results = await asyncio.gather(*[_browse_one(m) for m in q_months])

        # 合并三个月结果，按 id 去重
        seen_ids = set()
        items = []
        for m_items in monthly_results:
            for item in m_items:
                sid = item.get("id")
                if sid and sid not in seen_ids:
                    seen_ids.add(sid)
                    items.append(item)

        if not items:
            logger.warning(f"{year}年{month}季度 搜索结果为空")
            return {}

        logger.info(f"共找到 {len(items)} 个条目，开始获取详情（并发={max_concurrency}）")

        all_data = {}

        async def _fetch_one(item: dict):
            sid = item["id"]
            name = item.get('name_cn') or item['name']
            logger.debug(f"获取 {name} ({sid})")
            anime = await self.fetch_anime_by_id(sid)
            if anime:
                all_data[str(anime["id"])] = anime

        if max_concurrency > 1:
            sem = asyncio.Semaphore(max_concurrency)

            async def _fetch_with_limit(item):
                async with sem:
                    await _fetch_one(item)
                    await asyncio.sleep(random.uniform(0.5, 1.5))

            await asyncio.gather(*[_fetch_with_limit(item) for item in items])
        else:
            for i, item in enumerate(items):
                await _fetch_one(item)
                if i < len(items) - 1:
                    await asyncio.sleep(random.uniform(0.5, 1.5))

        return all_data

    async def _enrich_characters(self, characters: list) -> list:
        """为角色列表补充译名"""
        enriched = []
        for i, c in enumerate(characters):
            cid = c.get("id")
            translated = ""
            if cid:
                detail = await self._get(f"/v0/characters/{cid}")
                if detail:
                    infobox = detail.get("infobox", []) or []
                    for item in infobox:
                        raw = item.get("value")
                        if item.get("key") == "简体中文名" and raw:
                            if isinstance(raw, str):
                                translated = raw.strip()
                            elif isinstance(raw, list) and raw:
                                translated = str(raw[0] if isinstance(raw[0], str) else raw[0].get("v", "")).strip()
                            break
                # 请求间隔
                if i < len(characters) - 1:
                    await asyncio.sleep(0.3)
            c["translated_name"] = translated
            enriched.append(c)
        return enriched

    def _assemble_anime_data(self, subject: dict, persons: list, characters: list) -> dict:
        """数据组装为兼容格式"""
        name_cn = subject.get("name_cn", "") or ""
        name_jp = subject.get("name", "")

        # 媒体类型
        media_type = "tv"
        platform = (subject.get("platform") or "").lower()
        if platform in ("movie", "film", "剧场版"):
            media_type = "movie"
        elif platform in ("web", "ova"):
            media_type = platform

        # 评分
        rating = subject.get("rating", {}) or {}
        score = rating.get("score", 0)
        votes = rating.get("total", 0)
        rank_val = rating.get("rank", 0)
        score_desc = self._score_description(score)

        # 标签
        tags = [
            {"name": t["name"], "count": t.get("count", 0)}
            for t in (subject.get("tags", []) or [])
        ]

        # 封面
        images = subject.get("images", {}) or {}
        cover = images.get("large", "") or images.get("common", "")

        # infobox 解析（放送星期、别名）
        infobox = subject.get("infobox", []) or []
        broadcast_day = ""
        aliases = []
        for item in infobox:
            key = item.get("key", "")
            raw = item.get("value")
            if not raw:
                continue

            if isinstance(raw, str):
                value = raw.strip()
                if key == "放送星期" and value:
                    broadcast_day = value
                elif key in ("别名", "其他译名", "别称") and value:
                    for a in value.split(","):
                        a = a.strip()
                        if a:
                            aliases.append(a)

            elif isinstance(raw, list):
                values = []
                for v in raw:
                    if isinstance(v, dict) and v.get("v"):
                        values.append(v["v"].strip())
                if key == "放送星期" and values:
                    broadcast_day = values[0]
                elif key in ("别名", "其他译名", "别称"):
                    aliases.extend(values)

        # 话数
        eps = subject.get("eps", 0) or subject.get("total_episodes", 0) or 0
        eps_str = str(eps) if eps else ""

        # 日期
        date = subject.get("date", "") or ""

        # Staff 组装
        staff = {
            "director": [],
            "script": [],
            "storyboard": [],
            "episode_director": [],
            "music": [],
            "character_design": [],
            "series_composition": [],
        }
        production_companies = []

        for p in persons:
            relation = (p.get("relation") or "").strip()
            name = p.get("name", "")
            if not relation or not name:
                continue

            # 动画制作 / 製作
            if relation in ("动画制作", "製作", "制作"):
                production_companies.append(name)
                continue

            # 按 relation 映射到 staff 角色
            mapped = STAFF_ROLE_MAPPING.get(relation)
            if mapped and mapped in staff:
                staff[mapped].append(name)
            else:
                # 未知关系放到对应键
                if relation not in staff:
                    staff[relation] = []
                staff[relation].append(name)

        # 角色 + CV 组装
        char_list = []
        for c in characters:
            actors = c.get("actors", []) or []
            cv_name = actors[0].get("name", "") if actors else ""
            char_list.append({
                "id": str(c.get("id", "")) if c.get("id") is not None else "",
                "original_name": c.get("name", ""),
                "translated_name": c.get("translated_name", ""),
                "role": (c.get("relation") or "配角") if c.get("relation") else "配角",
                "cv": cv_name,
                "image_url": (c.get("images", {}) or {}).get("large", ""),
            })

        return {
            "id": str(subject["id"]),
            "title_cn": name_cn,
            "title_jp": name_jp,
            "cover_url": cover,
            "basic_info": {
                "original_title": name_jp,
                "chinese_title": name_cn,
                "start_date": date,
                "episodes": eps_str,
                "media_type": media_type,
                "broadcast_day": broadcast_day,
            },
            "rating": {
                "score": float(score) if score else 0,
                "votes": votes,
                "rank": rank_val,
                "description": score_desc,
            },
            "production": {
                "animation_production": production_companies,
            },
            "staff": staff,
            "characters": char_list,
            "tags": tags,
            "aliases": aliases,
        }

    @staticmethod
    def _score_description(score: float) -> str:
        if score <= 0:
            return ""
        if score >= 8.5:
            return "神作"
        if score >= 7.5:
            return "力荐"
        if score >= 6.5:
            return "推荐"
        if score >= 5.5:
            return "还行"
        if score >= 4.5:
            return "不过不失"
        if score >= 3.5:
            return "较差"
        if score >= 2.5:
            return "差"
        if score >= 1.5:
            return "很差"
        return "不忍直视"
