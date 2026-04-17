import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "123456789").split(",")))

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bot_data.db")

# Admin Web Panel
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "supersecretkey123")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
ADMIN_PORT = int(os.getenv("ADMIN_PORT", "5000"))

# Payment info (bank transfer)
BANK_NAME = os.getenv("BANK_NAME", "MB Bank")
BANK_ACCOUNT = os.getenv("BANK_ACCOUNT", "0123456789")
BANK_OWNER = os.getenv("BANK_OWNER", "NGUYEN VAN A")
BANK_BRANCH = os.getenv("BANK_BRANCH", "Hà Nội")

# Bot settings
MIN_DEPOSIT = int(os.getenv("MIN_DEPOSIT", "10000"))
BOT_NAME = os.getenv("BOT_NAME", "Shop Mã Xã Hội Bot")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "@admin_support")
