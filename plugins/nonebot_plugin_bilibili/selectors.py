from __future__ import annotations

from pathlib import Path
from collections.abc import Callable, Awaitable

from .database import repository
from .paths import FONT_DIR, TEMPLATE_DIR
from .models import PushContent, RenderSelection

FontSelector = Callable[[int, PushContent], Awaitable[Path | None]]
TemplateSelector = Callable[[int, PushContent], Awaitable[Path | None]]
ColorSelector = Callable[[int, PushContent], Awaitable[str | None]]
GradientSelector = Callable[[int, PushContent], Awaitable[str | None]]


def _render_kind(content: PushContent) -> str:
    if content.kind.value in {"music", "article"}:
        return "dynamic"
    return content.kind.value


def _safe_child(directory: Path, name: str | None) -> Path | None:
    if not name:
        return None
    path = (directory / Path(name).name).resolve()
    if path.parent != directory.resolve() or not path.is_file():
        return None
    return path


async def _default_font_selector(group_id: int, content: PushContent) -> Path | None:
    _, font_name, _, _ = await repository.resolve_override(group_id, _render_kind(content))
    return _safe_child(FONT_DIR, font_name)


async def _default_template_selector(group_id: int, content: PushContent) -> Path | None:
    template_name, _, _, _ = await repository.resolve_override(group_id, _render_kind(content))
    return _safe_child(TEMPLATE_DIR, template_name)


async def _default_color_selector(group_id: int, content: PushContent) -> str | None:
    _, _, color, _ = await repository.resolve_override(group_id, _render_kind(content))
    return color


async def _default_gradient_selector(group_id: int, content: PushContent) -> str | None:
    _, _, _, gradient = await repository.resolve_override(group_id, _render_kind(content))
    return gradient


_font_selector: FontSelector = _default_font_selector
_template_selector: TemplateSelector = _default_template_selector
_color_selector: ColorSelector = _default_color_selector
_gradient_selector: GradientSelector = _default_gradient_selector


def register_font_selector(selector: FontSelector) -> None:
    global _font_selector
    _font_selector = selector


def register_template_selector(selector: TemplateSelector) -> None:
    global _template_selector
    _template_selector = selector


def register_color_selector(selector: ColorSelector) -> None:
    global _color_selector
    _color_selector = selector


def register_gradient_selector(selector: GradientSelector) -> None:
    global _gradient_selector
    _gradient_selector = selector


async def select_render_assets(group_id: int, content: PushContent) -> RenderSelection:
    template = await _template_selector(group_id, content)
    font = await _font_selector(group_id, content)
    color = await _color_selector(group_id, content)
    gradient = await _gradient_selector(group_id, content)
    return RenderSelection(
        template_path=str(template) if template else None,
        font_path=str(font) if font else None,
        accent_color=color,
        gradient_color=gradient,
    )
