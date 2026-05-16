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

    _max_records: int = 50

    _instance: "ScreenObservationStore | None" = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: list[ScreenObservation] = []

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
            self._records.append(observation)
            self._prune_locked(observation.timestamp)

    def get_latest(self, now_ts: float) -> ScreenObservation | None:
        """获取未过期的最新观测。"""
        with self._lock:
            self._prune_locked(now_ts)
            if not self._records:
                return None
            return self._records[-1]

    def get_recent_valid(self, now_ts: float, limit: int) -> list[ScreenObservation]:
        """获取最近若干条未过期观测。"""
        with self._lock:
            self._prune_locked(now_ts)
            if limit <= 0 or not self._records:
                return []
            return list(self._records[-limit:])

    def clear(self) -> None:
        """清空缓存。"""
        with self._lock:
            self._records = []

    def _prune_locked(self, now_ts: float) -> None:
        """清理过期和过多的历史观测。"""
        self._records = [item for item in self._records if item.expires_at > now_ts]
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
