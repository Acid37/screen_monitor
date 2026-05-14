"""screen_monitor 插件入口。"""

from __future__ import annotations

from src.app.plugin_system.base import BasePlugin, register_plugin
from src.app.plugin_system.api.log_api import get_logger
from src.kernel.concurrency import get_task_manager
from src.kernel.scheduler import get_unified_scheduler, TriggerType

from .config import ScreenMonitorConfig
from .event_handler import ScreenMonitorStartupHandler
from .service import ScreenMonitorService

logger = get_logger("screen_monitor")

@register_plugin
class ScreenMonitorPlugin(BasePlugin):
    plugin_name: str = "screen_monitor"
    plugin_description: str = "主人屏幕动态实时视觉监测插件，结合VLM分析提供弱注入背景"
    plugin_version: str = "1.0.0"

    configs: list[type] = [ScreenMonitorConfig]
    dependent_components: list[str] = []

    def __init__(self, config: ScreenMonitorConfig | None = None) -> None:
        super().__init__(config)
        self.scheduler = get_unified_scheduler()
        self.trigger_type = TriggerType.TIME
        self.schedule_id: str | None = None
        self._startup_task_id: str | None = None
        self._service: ScreenMonitorService | None = None

    def get_components(self) -> list[type]:
        return [ScreenMonitorService, ScreenMonitorStartupHandler]

    async def on_plugin_loaded(self) -> None:
        if isinstance(self.config, ScreenMonitorConfig) and self.config.monitor.enabled:
            self._service = ScreenMonitorService(self)
            old_status = await self._service.storage.get_valid_status()
            if old_status:
                self._service.update_observation(old_status, self.config.monitor.retention_hours)

            if self.config.monitor.log_enabled:
                logger.info(
                    f"Screen monitor plugin loaded, waiting for scheduler start: "
                    f"interval={self.config.monitor.interval_minutes}m, "
                    f"model_task={self.config.model.model_task}, "
                    f"models={self.config.model.models or ['<use task>']}, "
                    f"save_screenshot={self.config.monitor.save_screenshot}"
                )
        else:
            logger.info("Screen monitor is disabled by config")

    async def on_plugin_unloaded(self) -> None:
        if self.schedule_id:
            await self.scheduler.delete_schedule(self.schedule_id)
            self.schedule_id = None
        if self._startup_task_id:
            try:
                get_task_manager().cancel_task(self._startup_task_id)
            except Exception:
                pass
            self._startup_task_id = None
        if self._service is not None:
            self._service.clear_observation()