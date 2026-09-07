from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.filters import Command

from services.supabase_client import get_student, upload_homework_photo, create_submission, get_homeworks
from keyboards.main_menu import get_main_menu

router = Router()


@router.message(Command("send"))
async def cmd_send(message: Message):
    """Подсказка, как отправить домашнее задание."""
    await message.answer(
        "📸 Просто отправьте фото вашего домашнего задания прямо в этот чат.\n\n"
        "Я автоматически сохраню его и передам учителю.",
        reply_markup=get_main_menu()
    )


@router.message(F.photo)
async def process_homework_photo(message: Message, bot: Bot):
    """Обработка фото домашнего задания."""
    
    # Проверяем, зарегистрирован ли ученик
    student = await get_student(message.from_user.id)
    if not student:
        await message.answer(
            "❌ Вы ещё не зарегистрированы!\n\n"
            "Отправьте /start, чтобы пройти регистрацию."
        )
        return
    
    # Скачиваем фото
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    
    # Генерируем имя файла
    import uuid
    from datetime import datetime
    filename = f"{student['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.jpg"
    
    # Загружаем в Storage
    try:
        photo_url = await upload_homework_photo(file_bytes.read(), filename)
    except Exception as e:
        await message.answer(f"❌ Ошибка загрузки фото: {e}\nПопробуйте ещё раз.")
        return
    
    # Сохраняем в БД
    submission_data = {
        "student_id": student["id"],
        "photo_url": photo_url,
        "status": "pending"
    }
    
    try:
        await create_submission(submission_data)
    except Exception as e:
        await message.answer(f"❌ Ошибка сохранения: {e}")
        return
    
    await message.answer(
        f"✅ Домашнее задание получено!\n\n"
        f"👤 {student['first_name']} {student['last_name']}\n"
        f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"Учитель скоро проверит вашу работу.",
        reply_markup=get_main_menu()
    )
