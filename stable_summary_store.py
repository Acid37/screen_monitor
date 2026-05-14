"""screen_monitor 稳定摘要缓存。"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass(slots=True)
class StableSummary:
    """稳定摘要数据。"""

    text: str = ""
    updated_at: float = 0.0
    source_texts: list[str] = field(default_factory=list)


class StableSummaryStore:
    """稳定摘要单例缓存。"""

    _instance: "StableSummaryStore | None" = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._summary = StableSummary()

    @classmethod
    def get_instance(cls) -> "StableSummaryStore":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def get(self) -> StableSummary:
        with self._lock:
            return StableSummary(
                text=self._summary.text,
                updated_at=self._summary.updated_at,
                source_texts=list(self._summary.source_texts),
            )

    def should_refresh(self, source_texts: list[str], min_refresh_minutes: int) -> bool:
        with self._lock:
            if self._summary.text == "":
                return True
            if self._summary.source_texts != source_texts:
                return True
            min_seconds = max(0, min_refresh_minutes) * 60
            return (time.time() - self._summary.updated_at) >= min_seconds

    def update(self, text: str, source_texts: list[str]) -> None:
        with self._lock:
            self._summary = StableSummary(
                text=text,
                updated_at=time.time(),
                source_texts=list(source_texts),
            )

    def clear(self) -> None:
        with self._lock:
            self._summary = StableSummary()
