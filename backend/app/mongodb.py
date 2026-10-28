from motor.motor_asyncio import AsyncIOMotorClient
from .config import get_settings

class MongoDB:
    client: AsyncIOMotorClient = None
    db = None

    def connect(self):
        settings = get_settings()
        self.client = AsyncIOMotorClient(settings.mongodb_uri)
        self.db = self.client[settings.db_name]

    def close(self):
        self.client.close()

db_manager = MongoDB()
