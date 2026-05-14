import time
from src.kernel.storage import JSONStore

class ScreenMonitorStorage:
    def __init__(self):
        self.store = JSONStore(storage_dir="data/screen_monitor")
        self.key = "latest_status"
        
    async def save_status(self, text: str, retention_hours: int):
        expires_at = time.time() + retention_hours * 3600
        data = {
            "status": text,
            "timestamp": time.time(),
            "expires_at": expires_at
        }
        await self.store.save(self.key, data)
        
    async def get_valid_status(self) -> str | None:
        if await self.store.exists(self.key):
            data = await self.store.load(self.key)
            if time.time() < data.get("expires_at", 0):
                return data.get("status")
        return None
