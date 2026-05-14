"""screen_monitor 服务组件。"""

from __future__ import annotations

import asyncio
import base64
import io
import time
from pathlib import Path
from typing import TYPE_CHECKING

import mss
from PIL import Image as PilImage
from PIL import ImageChops, ImageStat

from src.app.plugin_system.base import BaseService
from src.app.plugin_system.api.llm_api import get_model_set_by_name, get_model_set_by_task
from src.app.plugin_system.api.log_api import get_logger
from src.app.plugin_system.api.prompt_api import add_system_reminder
from src.kernel.llm import LLMRequest, ROLE
from src.kernel.llm.payload import Image, LLMPayload, Text

from .config import ScreenMonitorConfig
from .observation_store import ScreenObservation, ScreenObservationStore
from .storage import ScreenMonitorStorage

if TYPE_CHECKING:
    from .plugin import ScreenMonitorPlugin

_SCREEN_REMINDER_BUCKET = "actor"
_SCREEN_REMINDER_NAME = "屏幕观察"

logger = get_logger("screen_monitor")


class ScreenMonitorService(BaseService):
    """屏幕监控核心服务。"""

    service_name: str = "screen_monitor"
    service_description: str = "定时截屏、变化检测、VLM 分析与提醒注入服务"
    dependencies: list[str] = []

    def __init__(self, plugin: "ScreenMonitorPlugin") -> None:
        """初始化服务。"""
        super().__init__(plugin)
        self.storage = ScreenMonitorStorage()
        self.observation_store = ScreenObservationStore.get_instance()
        self.last_thumbnail: PilImage.Image | None = None
        self.screenshot_dir = Path("data/screenshots")

    def _info(self, message: str) -> None:
        """按配置输出 info 日志。"""
        config = getattr(self.plugin, "config", None)
        if isinstance(config, ScreenMonitorConfig) and config.monitor.log_enabled:
            logger.info(message)

    def update_observation(self, text: str, retention_hours: int) -> None:
        """更新最新屏幕观测缓存并同步到 system reminder。"""
        now_ts = time.time()
        had_previous = self.observation_store.get_latest(now_ts) is not None
        self.observation_store.set_latest(
            ScreenObservation(
                text=text,
                timestamp=now_ts,
                expires_at=now_ts + retention_hours * 3600,
            )
        )

        # 同步写入 system reminder，由框架自动注入到所有 chatter 的 LLM 上下文
        reminder_text = self._build_reminder_text()
        if reminder_text:
            add_system_reminder(_SCREEN_REMINDER_BUCKET, _SCREEN_REMINDER_NAME, reminder_text)
        else:
            # 观测已过期，清理 reminder 避免注入过时信息
            from src.core.prompt import get_system_reminder_store
            get_system_reminder_store().delete(_SCREEN_REMINDER_BUCKET, _SCREEN_REMINDER_NAME)

        if not had_previous:
            self._info("[Screen Monitor] 首条屏幕观察已就绪，已通过 system reminder 全局注入")

    def _build_reminder_text(self) -> str:
        """构建注入到 system reminder 的屏幕观察文本。"""
        config = getattr(self.plugin, "config", None)
        if not isinstance(config, ScreenMonitorConfig):
            return ""

        observation = self.observation_store.get_latest(time.time())
        if observation is None:
            return ""

        return config.inject.prompt_template.format(observation=observation.text)

    def clear_observation(self) -> None:
        """清理最新屏幕观测缓存及 system reminder。"""
        self.observation_store.clear()
        from src.core.prompt import get_system_reminder_store
        get_system_reminder_store().delete(_SCREEN_REMINDER_BUCKET, _SCREEN_REMINDER_NAME)

    def capture_screen_sync(self) -> tuple[str, PilImage.Image, str | None] | None:
        """同步截屏并返回图像与差异缩略图。"""
        try:
            config = getattr(self.plugin, "config", None)
            if not isinstance(config, ScreenMonitorConfig):
                return None

            with mss.mss() as sct:
                monitor_index = config.monitor.monitor_index
                if monitor_index <= 0 or monitor_index >= len(sct.monitors):
                    monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                else:
                    monitor = sct.monitors[monitor_index]
                sct_img = sct.grab(monitor)
                img = PilImage.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                img.thumbnail((config.monitor.image_max_width, config.monitor.image_max_height))

                diff_thumb = img.copy()
                diff_thumb.thumbnail((64, 64))
                diff_thumb = diff_thumb.convert("L")

                saved_path: str | None = None
                if config.monitor.save_screenshot:
                    self.screenshot_dir.mkdir(parents=True, exist_ok=True)
                    filename = f"screen_monitor_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
                    file_path = self.screenshot_dir / filename
                    img.save(file_path, format="JPEG", quality=config.monitor.jpeg_quality)
                    saved_path = str(file_path)

                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=config.monitor.jpeg_quality)
                b64_str = (
                    "data:image/jpeg;base64,"
                    f"{base64.b64encode(buffer.getvalue()).decode('utf-8')}"
                )
                return b64_str, diff_thumb, saved_path
        except Exception as exc:
            logger.error(f"[Screen Monitor] Capture failed: {exc}")
            return None

    def resolve_model_set(self, config: ScreenMonitorConfig):
        """解析本次使用的模型集合。"""
        if config.model.models:
            model_set = []
            for model_name in config.model.models:
                model_set.extend(
                    get_model_set_by_name(
                        model_name,
                        temperature=config.model.temperature,
                        max_tokens=config.model.max_tokens,
                    )
                )
            return model_set
        return get_model_set_by_task(config.model.model_task)

    async def run_monitor_task(self) -> None:
        """执行一次屏幕监控任务。"""
        config = getattr(self.plugin, "config", None)
        if not isinstance(config, ScreenMonitorConfig) or not config.monitor.enabled:
            return

        try:
            self._info("[Screen Monitor] 开始执行周期截屏任务")
            result = await asyncio.to_thread(self.capture_screen_sync)
            if not result:
                self._info("[Screen Monitor] 截屏失败，已跳过本轮分析")
                return
            b64_img, current_thumb, saved_path = result
            if saved_path:
                self._info(f"[Screen Monitor] 截图已保存: {saved_path}")

            if self.last_thumbnail is not None:
                diff = ImageChops.difference(self.last_thumbnail, current_thumb)
                stat = ImageStat.Stat(diff)
                if stat.mean[0] < config.monitor.diff_threshold:
                    self._info(
                        f"[Screen Monitor] 画面无显著变动(差异值:{stat.mean[0]:.2f})，跳过VLM分析"
                    )
                    old_status = await self.storage.get_valid_status()
                    if old_status:
                        await self.storage.save_status(
                            old_status,
                            config.monitor.retention_hours,
                        )
                        self.update_observation(old_status, config.monitor.retention_hours)
                    return

            self.last_thumbnail = current_thumb
            model_set = self.resolve_model_set(config)
            if not model_set:
                logger.error("[Screen Monitor] 未找到可用视觉模型，请检查 model.toml 或插件配置")
                return

            model_desc = (
                ", ".join(config.model.models)
                if config.model.models
                else f"task:{config.model.model_task}"
            )
            self._info(f"[Screen Monitor] 使用模型: {model_desc}")

            request = LLMRequest(model_set=model_set, request_name="screen_monitor_analysis")
            request.add_payload(
                LLMPayload(ROLE.USER, [Text(config.monitor.prompt), Image(b64_img)])
            )

            response = await request.send(stream=False)
            await response
            result_text = (response.message or "").replace("\n", " ").strip()
            self._info(f"[Screen Monitor] 分析结果: {result_text}")

            await self.storage.save_status(result_text, config.monitor.retention_hours)
            self.update_observation(result_text, config.monitor.retention_hours)
            self._info("[Screen Monitor] 状态已写入存储并更新 observation cache")
        except Exception as exc:
            logger.error(f"[Screen Monitor] task failed: {exc}")
