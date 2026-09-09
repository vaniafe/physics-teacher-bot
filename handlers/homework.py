from aiogram import Router, F, Bot
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from services.supabase_client import (
    get_student, upload_homework_photo, create_submission,
    check_avatar_update_needed, update_avatar
)
from keyboards.main_menu import get_main_menu

router = Router()


class HomeworkSubmission(StatesGroup):
    photo = State()
    due_date = State()


class AvatarUpdate(StatesGroup):
    photo = State()


@router.message(Command("send"))
async def cmd_send(message: Message):
    """Подсказка, как отправить домашнее задание."""
    await message.answer(
        "📸 Просто отправьте фото вашего домашнего задания прямо в этот чат.\n\n"
        "Я спрошу дату, на которую оно задано, и сохраню всё.",
        reply_markup=get_main_menu()
    )


@router.message(F.photo)
async def process_homework_photo(message: Message, state: FSMContext, bot: Bot):
    """Обработка фото — либо домашка, либо обновление аватарки."""
    
    # Проверяем, зарегистрирован ли ученик
    student = await get_student(message.from_user.id)
    if not student:
        await message.answer(
            "❌ Вы ещё не зарегистрированы!\n\n"
            "Отправьте /start, чтобы пройти регистрацию."
        )
        return
    
    # Проверяем, не требуется ли обновление аватарки
    needs_update = await check_avatar_update_needed(message.from_user.id)
    if needs_update:
        # Если мы уже ждём фото для аватарки
        current_state = await state.get_state()
        if current_state == AvatarUpdate.photo:
            await process_avatar_update(message, state, bot, student)
            return
        
        # Первое фото после запроса — предлагаем обновить аватарку
        await message.answer(
            "📸 Учитель просит вас обновить фотографию профиля!\n\n"
            "Пожалуйста, отправьте новое фото вашего лица (аватарку). "
            "После этого вы сможете снова отправлять домашние задания.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="📷 Отправить новое фото")]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
        )
        await state.set_state(AvatarUpdate.photo)
        return
    
    # Если мы уже в процессе отправки домашки (ждём дату) — игнорируем новое фото
    current_state = await state.get_state()
    if current_state == HomeworkSubmission.due_date:
        await message.answer("⏳ Сначала укажите дату для предыдущего фото, или нажмите /cancel")
        return
    
    # Скачиваем фото домашки
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    
    # Сохраняем фото и student_id во временные данные
    await state.update_data(
        student_id=student["id"],
        photo_bytes=file_bytes.read(),
        file_id=photo.file_id
    )
    
    # Предлагаем быстрые варианты дат
    from datetime import datetime, timedelta
    today = datetime.now()
    dates = [
        today.strftime("%d.%m.%Y"),
        (today + timedelta(days=1)).strftime("%d.%m.%Y"),
        (today - timedelta(days=1)).strftime("%d.%m.%Y"),
    ]
    buttons = [[KeyboardButton(text=d)] for d in dates]
    buttons.append([KeyboardButton(text="📝 Ввести вручную")])
    keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)
    
    await message.answer(
        "📅 На какую дату задано это домашнее задание?\n\n"
        "Выберите дату или введите вручную в формате ДД.ММ.ГГГГ (например: 15.09.2026):",
        reply_markup=keyboard
    )
    await state.set_state(HomeworkSubmission.due_date)


async def process_avatar_update(message: Message, state: FSMContext, bot: Bot, student: dict):
    """Обработка новой аватарки."""
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    
    # Генерируем имя файла
    import uuid
    filename = f"{message.from_user.id}_{uuid.uuid4().hex[:8]}.jpg"
    
    # Загружаем в Storage
    try:
        from services.supabase_client import upload_avatar
        avatar_url = await upload_avatar(file_bytes.read(), filename)
    except Exception as e:
        await message.answer(f"❌ Ошибка загрузки фото: {e}\nПопробуйте ещё раз.")
        return
    
    # Обновляем в БД
    try:
        await update_avatar(message.from_user.id, avatar_url)
    except Exception as e:
        await message.answer(f"❌ Ошибка сохранения: {e}")
        return
    
    await state.clear()
    await message.answer(
        "✅ Фотография профиля обновлена!\n\n"
        "Теперь вы можете снова отправлять домашние задания.",
        reply_markup=get_main_menu()
    )


@router.message(HomeworkSubmission.due_date, F.text == "📝 Ввести вручную")
async def ask_manual_date(message: Message, state: FSMContext):
    await message.answer("Введите дату в формате ДД.ММ.ГГГГ:", reply_markup=get_main_menu())


@router.message(HomeworkSubmission.due_date)
async def process_due_date(message: Message, state: FSMContext):
    """Сохранение фото с указанной датой."""
    from datetime import datetime
    import uuid
    
    date_text = message.text.strip()
    
    # Парсим дату
    due_date = None
    for fmt in ("%d.%m.%Y", "%d.%m.%y"):
        try:
            due_date = datetime.strptime(date_text, fmt).date()
            break
        except ValueError:
            continue
    
    if not due_date:
        await message.answer(
            "❌ Неверный формат даты. Введите в формате ДД.ММ.ГГГГ (например: 15.09.2026):"
        )
        return
    
    data = await state.get_data()
    student_id = data["student_id"]
    file_bytes = data["photo_bytes"]
    
    # Генерируем имя файла
    filename = f"{student_id}_{due_date.strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}.jpg"
    
    # Загружаем в Storage
    try:
        photo_url = await upload_homework_photo(file_bytes, filename)
    except Exception as e:
        await message.answer(f"❌ Ошибка загрузки фото: {e}\nПопробуйте ещё раз.")
        await state.clear()
        return
    
    # Сохраняем в БД
    submission_data = {
        "student_id": student_id,
        "photo_url": photo_url,
        "due_date": due_date.isoformat(),
        "status": "pending"
    }
    
    try:
        await create_submission(submission_data)
    except Exception as e:
        await message.answer(f"❌ Ошибка сохранения: {e}")
        await state.clear()
        return
    
    await state.clear()
    await message.answer(
        f"✅ Домашнее задание получено!\n\n"
        f"📅 Дата: {due_date.strftime('%d.%m.%Y')}\n"
        f"📸 Фото сохранено.\n\n"
        f"Если нужно отправить ещё фото на ту же дату — просто пришлите следующее.",
        reply_markup=get_main_menu()
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отменено.", reply_markup=get_main_menu())
