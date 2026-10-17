"""Run from project root: python -m backend.scripts.seed (with PYTHONPATH=backend)."""
from pymongo import MongoClient
from app.config import get_settings
from app.database import create_indexes
from app.services.seed import seed_demo

if __name__ == '__main__':
    settings = get_settings()
    if not settings.demo_mode:
        raise SystemExit('Seed is disabled: set DEMO_MODE=true in a development environment.')
    with MongoClient(settings.mongodb_uri, tz_aware=True) as client:
        db = client[settings.mongodb_database]
        create_indexes(db)
        seed_demo(db)
        print('Seeded labelled demo accounts and 18 animals. No existing records were overwritten.')
