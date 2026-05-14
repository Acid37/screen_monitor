"""screen_monitor 观测结果存储。"""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(slots=True)
class ScreenObservation:
    """单条屏幕观测结果。"""

    text: str
    timestamp: float
    expires_at: float


class ScreenObservationStore:
    """进程内屏幕观测缓存。"""

    _instance: "ScreenObservationStore | None" = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest: ScreenObservation | None = None

    @classmethod
    def get_instance(cls) -> "ScreenObservationStore":
        """获取全局单例。"""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def set_latest(self, observation: ScreenObservation) -> None:
        """写入最新观测。"""
        with self._lock:
            self._latest = observation

    def get_latest(self, now_ts: float) -> ScreenObservation | None:
        """获取未过期的最新观测。"""
        with self._lock:
            if self._latest is None:
                return None
            if self._latest.expires_at <= now_ts:
                self._latest = None
                return None
            return self._latest

    def clear(self) -> None:
        """清空缓存。"""
        with self._lock:
            self._latest = None
