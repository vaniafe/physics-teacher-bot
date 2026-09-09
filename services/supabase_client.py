import asyncio
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


async def student_exists(telegram_id: int) -> bool:
    """Проверяет, зарегистрирован ли уже ученик."""
    result = await asyncio.to_thread(
        lambda: supabase.table("students").select("id").eq("telegram_id", telegram_id).execute()
    )
    return len(result.data) > 0


async def create_student(data: dict) -> dict:
    """Создаёт запись ученика в БД."""
    result = await asyncio.to_thread(
        lambda: supabase.table("students").insert(data).execute()
    )
    return result.data[0] if result.data else None


async def get_student(telegram_id: int) -> dict:
    """Получает данные ученика по telegram_id."""
    result = await asyncio.to_thread(
        lambda: supabase.table("students").select("*").eq("telegram_id", telegram_id).execute()
    )
    return result.data[0] if result.data else None


async def upload_avatar(file_bytes: bytes, filename: str) -> str:
    """Загружает аватарку в Supabase Storage. Возвращает публичный URL."""
    await asyncio.to_thread(
        lambda: supabase.storage.from_("avatars").upload(
            filename, file_bytes, {"content-type": "image/jpeg", "upsert": "true"}
        )
    )
    return supabase.storage.from_("avatars").get_public_url(filename)


async def upload_homework_photo(file_bytes: bytes, filename: str) -> str:
    """Загружает фото домашки в Supabase Storage. Возвращает публичный URL."""
    await asyncio.to_thread(
        lambda: supabase.storage.from_("homework-photos").upload(
            filename, file_bytes, {"content-type": "image/jpeg", "upsert": "true"}
        )
    )
    return supabase.storage.from_("homework-photos").get_public_url(filename)


async def create_submission(data: dict) -> dict:
    """Создаёт запись о сданной работе."""
    result = await asyncio.to_thread(
        lambda: supabase.table("submissions").insert(data).execute()
    )
    return result.data[0] if result.data else None

async def check_avatar_update_needed(telegram_id: int) -> bool:
    """Проверяет, нужно ли ученику обновить аватарку."""
    result = await asyncio.to_thread(
        lambda: supabase.table("students").select("needs_avatar_update").eq("telegram_id", telegram_id).execute()
    )
    if result.data and len(result.data) > 0:
        return result.data[0].get("needs_avatar_update", False)
    return False

async def update_avatar(telegram_id: int, avatar_url: str) -> None:
    """Обновляет аватарку и сбрасывает флаг."""
    await asyncio.to_thread(
        lambda: supabase.table("students").update({
            "avatar_url": avatar_url,
            "needs_avatar_update": False
        }).eq("telegram_id", telegram_id).execute()
    )


async def get_homeworks() -> list:
    """Получает список всех заданий."""
    result = await asyncio.to_thread(
        lambda: supabase.table("homeworks").select("*").order("due_date", desc=True).execute()
    )
    return result.data
