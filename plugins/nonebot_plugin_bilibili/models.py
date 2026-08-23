from __future__ import annotations

from enum import Enum
from typing import Any
from dataclasses import field, dataclass
from datetime import datetime, timezone, timedelta


class ContentKind(str, Enum):
    DYNAMIC = "dynamic"
    VIDEO = "video"
    MUSIC = "music"
    ARTICLE = "article"
    LIVE = "live"


class LiveAction(str, Enum):
    START = "start"
    STOP = "stop"


class AtAllKind(str, Enum):
    ALL = "all"
    DYNAMIC = "dynamic"
    VIDEO = "video"
    MUSIC = "music"
    ARTICLE = "article"
    LIVE = "live"


@dataclass(slots=True)
class Subscription:
    group_id: int
    uid: int
    uname: str = ""
    avatar: str = ""
    group_name: str = ""
    group_avatar: str = ""


@dataclass(slots=True, frozen=True)
class RichTextSegment:
    text: str
    emoji_url: str = ""


@dataclass(slots=True)
class PushContent:
    id: str
    uid: int
    kind: ContentKind
    title: str
    text: str
    url: str
    author_name: str
    author_avatar: str = ""
    cover: str = ""
    images: list[str] = field(default_factory=list)
    rich_text: list[RichTextSegment] = field(default_factory=list)
    published_at: int = 0
    live_action: LiveAction | None = None
    forward: PushContent | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    image_dimensions: list[tuple[int, int]] = field(default_factory=list)

    @property
    def filter_text(self) -> str:
        parts = [part for part in (self.title, self.text, self.author_name) if part]
        if self.forward:
            parts.append(self.forward.filter_text)
        return "\n".join(parts)

    @property
    def published_text(self) -> str:
        if not self.published_at:
            return ""
        bilibili_timezone = timezone(timedelta(hours=8))
        return datetime.fromtimestamp(self.published_at, bilibili_timezone).strftime(
            "%Y-%m-%d %H:%M"
        )


@dataclass(slots=True)
class RenderSelection:
    template_path: str | None
    font_path: str | None
    accent_color: str | None = None
    gradient_color: str | None = None


@dataclass(slots=True)
class LoginSession:
    key: str
    url: str
