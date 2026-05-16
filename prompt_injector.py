"""screen_monitor prompt 后置注入。"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from src.app.plugin_system.api.log_api import get_logger
from src.kernel.event import EventDecision

from .config import ScreenMonitorConfig
from .observation_store import ScreenObservationStore

logger = get_logger("screen_monitor")

_DEFAULT_CHATTER_PROMPT = "default_chatter_user_prompt"
_KFC_PROMPT = "kfc_user_prompt"
_VOICE_CHATTER_PROMPT = "voice_chatter_user_prompt"


def _normalize_names(names: list[str]) -> set[str]:
    """去除空白并返回名称集合。"""
    return {name for name in names if isinstance(name, str) and name.strip()}


def _resolve_target_prompt_names(config: ScreenMonitorConfig) -> set[str]:
    """解析当前可注入的 prompt 名称集合（静态参考值）。"""
    explicit_enabled = _normalize_names(config.inject.enabled_prompt_names)
    if explicit_enabled:
        return explicit_enabled.difference(_normalize_names(config.inject.disabled_prompt_names))

    static_targets = {
        _DEFAULT_CHATTER_PROMPT,
        _KFC_PROMPT,
        _VOICE_CHATTER_PROMPT,
    }
    return static_targets.difference(_normalize_names(config.inject.disabled_prompt_names))


def _format_observation_time(timestamp: float) -> str:
    """格式化观测时间点。"""
    dt = datetime.fromtimestamp(timestamp)
    now = datetime.now()
    if dt.date() == now.date():
        return dt.strftime("%H:%M:%S")
    return dt.strftime("%m-%d %H:%M:%S")


def _build_observation_lines(items: list[tuple[float, str]]) -> list[str]:
    """将观测记录转换为可注入的行文本。"""
    lines: list[str] = []
    for timestamp, text in items:
        cleaned_text = text.strip()
        if not cleaned_text:
            continue
        lines.append(f"- {_format_observation_time(timestamp)}：{cleaned_text}")
    return lines


def _render_prompt_template(template: str, observation_text: str, recent_count: int) -> str:
    """渲染注入模板。"""
    return (
        template.replace("{observation}", observation_text).replace("{recent_count}", str(recent_count))
    )


async def screen_monitor_prompt_injector(
    event_name: str, params: dict[str, Any]
) -> tuple[EventDecision, dict[str, Any]]:
    """在支持的 chatter prompt 构建时按目标模板注入屏幕观测。"""
    prompt_name = params.get("name")
    values: dict[str, Any] = params.get("values", {})
    plugin = params.get("plugin")
    config = getattr(plugin, "config", None)
    if not isinstance(config, ScreenMonitorConfig):
        return EventDecision.SUCCESS, params

    now_ts = time.time()
    store = ScreenObservationStore.get_instance()
    recent_observations = store.get_recent_valid(now_ts, config.inject.summary_max_items)
    if not recent_observations:
        if config.debug.log_injection_result:
            logger.info(f"未注入屏幕观察：prompt={prompt_name}，原因=无有效 observation")
        return EventDecision.SUCCESS, params

    target_prompt_names = _resolve_target_prompt_names(config)
    if prompt_name not in target_prompt_names:
        if config.debug.log_injection_result:
            logger.info(f"未注入屏幕观察：prompt={prompt_name}，原因=不在可注入列表")
        return EventDecision.SUCCESS, params

    recent_items = [(item.timestamp, item.text) for item in recent_observations]
    observation_lines = _build_observation_lines(recent_items)
    if not observation_lines:
        if config.debug.log_injection_result:
            logger.info(f"未注入屏幕观察：prompt={prompt_name}，原因=无可注入内容")
        return EventDecision.SUCCESS, params

    injected_text = _render_prompt_template(
        config.inject.prompt_template,
        "\n".join(observation_lines),
        len(observation_lines),
    )

    existing_extra: str = values.get("extra", "") or ""
    separator = "\n\n" if existing_extra else ""
    values["extra"] = existing_extra + separator + injected_text
    params["values"] = values
    if config.debug.log_injection_result:
        logger.info(f"已向 prompt={prompt_name} 后置注入屏幕观察")
    return EventDecision.SUCCESS, params