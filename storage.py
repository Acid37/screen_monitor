"""screen_monitor 状态持久化。"""

from __future__ import annotations

import time

from src.kernel.storage import JSONStore


class ScreenMonitorStorage:
    """屏幕监控状态存储。"""

    def __init__(self) -> None:
        self.store = JSONStore(storage_dir="data/screen_monitor")
        self.key = "latest_status"

    async def save_status(self, text: str, retention_seconds: int) -> None:
        """保存状态并指定秒级过期时间。"""
        expires_at = time.time() + max(0, retention_seconds)
        data = {
            "status": text,
            "timestamp": time.time(),
            "expires_at": expires_at
        }
        await self.store.save(self.key, data)

    async def get_valid_status(self) -> str | None:
        """获取仍然有效的状态。"""
        if await self.store.exists(self.key):
            data = await self.store.load(self.key)
            if time.time() < data.get("expires_at", 0):
                return data.get("status")
        return None
