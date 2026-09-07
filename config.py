import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # service_role key (bypass RLS)

# Proxy (опционально, для обхода блокировки Telegram API в РФ)
# Пример: socks5://user:pass@host:port
PROXY_URL = os.getenv("PROXY_URL")

# Storage buckets
AVATARS_BUCKET = "avatars"
HOMEWORK_BUCKET = "homework-photos"

if not all([BOT_TOKEN, SUPABASE_URL, SUPABASE_KEY]):
    raise ValueError("Не все переменные окружения заданы! Проверьте .env файл.")
