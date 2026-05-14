"""screen_monitor prompt 后置注入。"""

from __future__ import annotations

import time
from typing import Any

from src.app.plugin_system.api.log_api import get_logger
from src.core.prompt import PROMPT_BUILD_EVENT
from src.kernel.event import EventDecision

from .config import ScreenMonitorConfig
from .observation_store import ScreenObservationStore
from .stable_summary_store import StableSummaryStore

logger = get_logger("screen_monitor")

_DEFAULT_CHATTER_PROMPT = "default_chatter_user_prompt"
_KFC_PROMPT = "kfc_user_prompt"


def _build_injected_text(observation_text: str) -> str:
    """构造注入文本。"""
    return f"近期屏幕观察：\n- {observation_text}"


def _build_stable_summary(source_texts: list[str]) -> str:
    """构造稳定摘要文本。"""
    bullet_lines = [f"- {text}" for text in source_texts if text.strip()]
    if not bullet_lines:
        return ""
    return "近期屏幕动态摘要：\n" + "\n".join(bullet_lines)


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

    observation = ScreenObservationStore.get_instance().get_latest(time.time())
    if observation is None:
        if config.debug.log_injection_result:
            logger.info(f"未注入屏幕观察：prompt={prompt_name}，原因=无有效 observation")
        return EventDecision.SUCCESS, params

    injected_text = _build_injected_text(observation.text)
    if config.inject.use_stable_summary:
        recent = ScreenObservationStore.get_instance().get_recent_valid(
            time.time(),
            config.inject.summary_max_items,
        )
        source_texts = [item.text for item in recent]
        stable_store = StableSummaryStore.get_instance()
        if stable_store.should_refresh(
            source_texts,
            config.inject.summary_min_refresh_minutes,
        ):
            summary_text = _build_stable_summary(source_texts)
            if summary_text:
                stable_store.update(summary_text, source_texts)
        stable_summary = stable_store.get().text
        if stable_summary:
            injected_text = stable_summary

    if prompt_name == _DEFAULT_CHATTER_PROMPT and config.inject.enable_default_chatter:
        existing_extra: str = values.get("extra", "") or ""
        separator = "\n\n" if existing_extra else ""
        values["extra"] = existing_extra + separator + injected_text
        params["values"] = values
        if config.debug.log_injection_result:
            logger.info("已向 default_chatter 后置注入屏幕观察")
        return EventDecision.SUCCESS, params

    if prompt_name == _KFC_PROMPT and config.inject.enable_kokoro_flow_chatter:
        existing_extra: str = values.get("extra", "") or ""
        separator = "\n\n" if existing_extra else ""
        values["extra"] = existing_extra + separator + injected_text
        params["values"] = values
        if config.debug.log_injection_result:
            logger.info("已向 kokoro_flow_chatter 追加屏幕观察 extra payload")
        return EventDecision.SUCCESS, params

    if config.debug.log_injection_result:
        logger.info(f"未注入屏幕观察：prompt={prompt_name}，原因=目标未启用或模板不匹配")
    return EventDecision.SUCCESS, params