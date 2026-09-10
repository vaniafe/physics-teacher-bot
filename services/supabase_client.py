import asyncio
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


async def student_exists(telegram_id: int) -> bool:
    """Проверяет, привязан ли этот Telegram-аккаунт к ученику."""
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


async def get_student_by_login(login: str) -> dict:
    """Получает ученика по логину (для входа «я уже зарегистрирован»)."""
    result = await asyncio.to_thread(
        lambda: supabase.table("students").select("*").eq("login", login).execute()
    )
    return result.data[0] if result.data else None


async def find_student_by_name(first_name: str, last_name: str) -> dict:
    """Ищет ученика по имени и фамилии БЕЗ учёта регистра."""
    result = await asyncio.to_thread(
        lambda: supabase.table("students").select("id")
        .ilike("first_name", first_name)
        .ilike("last_name", last_name)
        .execute()
    )
    return result.data[0] if result.data else None


async def login_taken(login: str, exclude_id=None) -> bool:
    """Проверяет, занят ли логин другим учеником."""
    query = supabase.table("students").select("id").eq("login", login)
    if exclude_id:
        query = query.neq("id", exclude_id)
    result = await asyncio.to_thread(lambda: query.execute())
    return len(result.data) > 0


async def update_student(student_id, data: dict) -> dict:
    """Обновляет поля ученика."""
    result = await asyncio.to_thread(
        lambda: supabase.table("students").update(data).eq("id", student_id).execute()
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
    """Создаёт запись о сданной работе (due_date — дата из календаря,
    submitted_at проставится автоматически)."""
    result = await asyncio.to_thread(
        lambda: supabase.table("submissions").insert(data).execute()
    )
    return result.data[0] if result.data else None


async def get_calendar_dates(school: str, class_number: str) -> list:
    """Отмеченные учителем даты сдачи для класса (календарь на сайте)."""
    result = await asyncio.to_thread(
        lambda: supabase.table("class_calendar").select("date")
        .eq("school", school).eq("class_number", class_number)
        .order("date").execute()
    )
    return [r["date"] for r in result.data]



def _storage_path(url: str, bucket: str):
    """Извлекает путь файла из публичного URL Supabase Storage."""
    if not url:
        return None
    marker = f"/object/public/{bucket}/"
    if marker not in url:
        return None
    return url.split(marker, 1)[1].split("?")[0]


async def delete_avatar(file_url: str):
    """Удаляет аватарку из Storage по её URL (старое фото профиля)."""
    path = _storage_path(file_url, "avatars")
    if path:
        await asyncio.to_thread(
            lambda: supabase.storage.from_("avatars").remove([path])
        )


async def delete_homework_photo(file_url: str):
    """Удаляет фото работы из Storage по её URL."""
    path = _storage_path(file_url, "homework-photos")
    if path:
        await asyncio.to_thread(
            lambda: supabase.storage.from_("homework-photos").remove([path])
        )
