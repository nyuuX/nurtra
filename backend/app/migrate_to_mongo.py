"""Script to migrate local JSON database (data/defisitku.json) to MongoDB."""

import json
from pathlib import Path
from pymongo import MongoClient
from .config import get_settings

def migrate():
    settings = get_settings()
    client = MongoClient(settings.mongodb_uri)
    db = client[settings.db_name]

    db_file = Path(settings.db_path)
    if not db_file.exists():
        print(f"File {db_file} not found.")
        return

    with open(db_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Migrate users
    users_data = data.get("users", {})
    if users_data:
        users_collection = db["users"]
        # Clear existing users or update
        for email, udata in users_data.items():
            udata["_id"] = email  # Use email as _id
            users_collection.replace_one({"_id": email}, udata, upsert=True)
        print(f"Migrated {len(users_data)} users to MongoDB.")

    # Migrate shared demo data if needed
    demo_data = {
        "_id": "__anonymous__",
        "profile": data.get("profile"),
        "days": data.get("days", []),
        "favorites": data.get("favorites", []),
        "recent_searches": data.get("recent_searches", [])
    }
    db["shared"].replace_one({"_id": "__anonymous__"}, demo_data, upsert=True)
    print("Migrated demo data to MongoDB.")

    client.close()

if __name__ == "__main__":
    migrate()
