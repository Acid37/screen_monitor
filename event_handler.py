"""screen_monitor 事件处理器。"""

from __future__ import annotations

import asyncio
from typing import Any

from src.app.plugin_system.base import BaseEventHandler
from src.app.plugin_system.api.log_api import get_logger
from src.core.components.types import EventType
from src.kernel.event import EventDecision
from src.kernel.concurrency import get_task_manager

from .config import ScreenMonitorConfig

logger = get_logger("screen_monitor")


async def _delayed_first_run(plugin: Any, delay_minutes: int) -> None:
    """后台执行首次延迟分析。"""
    if delay_minutes > 0:
        await asyncio.sleep(delay_minutes * 60)

    service = getattr(plugin, "_service", None)
    config = getattr(plugin, "config", None)
    if service is None or not isinstance(config, ScreenMonitorConfig):
        return

    if config.monitor.log_enabled:
        logger.info("开始执行首次屏幕分析")
    await service.run_monitor_task()


class ScreenMonitorStartupHandler(BaseEventHandler):
    """在调度器启动后注册 screen_monitor 周期任务。"""

    handler_name = "screen_monitor_startup"
    handler_description = "在 ON_START 后注册屏幕监控调度任务"
    init_subscribe = [EventType.ON_START]

    async def execute(
        self, event_name: str, params: dict[str, Any]
    ) -> tuple[EventDecision, dict[str, Any]]:
        """处理启动事件。"""
        plugin = self.plugin
        config = getattr(plugin, "config", None)
        service = getattr(plugin, "_service", None)

        if (
            isinstance(config, ScreenMonitorConfig)
            and config.monitor.enabled
            and service is not None
            and plugin.schedule_id is None
        ):
            plugin.schedule_id = await plugin.scheduler.create_schedule(
                callback=service.run_monitor_task,
                trigger_type=plugin.trigger_type,
                trigger_config={"interval_seconds": config.monitor.interval_minutes * 60},
                task_name="screen_monitor_job",
                is_recurring=True,
                callback_args=(),
            )
            if config.monitor.log_enabled:
                logger.info(
                    f"已注册屏幕监控调度：每 {config.monitor.interval_minutes} 分钟执行一次"
                )
                logger.info(
                    f"屏幕监控已启动：首次执行={config.monitor.run_once_on_start}，"
                    f"下次执行约 {config.monitor.interval_minutes} 分钟后"
                )

            if config.monitor.run_once_on_start:
                if config.monitor.log_enabled:
                    logger.info(
                        f"已启用首次执行：{config.monitor.run_once_delay_minutes} 分钟后开始首次分析"
                    )
                task = get_task_manager().create_task(
                    _delayed_first_run(plugin, config.monitor.run_once_delay_minutes),
                    name="screen_monitor_first_run",
                    daemon=True,
                )
                plugin._startup_task_id = task.task_id
            else:
                if config.monitor.log_enabled:
                    logger.info("未启用首次执行：本次启动后不立即分析")

        return EventDecision.SUCCESS, params