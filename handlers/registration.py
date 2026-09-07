from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from services.supabase_client import student_exists, create_student, upload_avatar
from keyboards.main_menu import get_main_menu

router = Router()


class Registration(StatesGroup):
    first_name = State()
    last_name = State()
    class_number = State()
    school = State()
    avatar = State()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Обработка команды /start."""
    await state.clear()
    
    if await student_exists(message.from_user.id):
        await message.answer(
            f"Привет, {message.from_user.first_name}!\n\n"
            "Вы уже зарегистрированы. Отправляйте фото домашнего задания — я сохраню его.",
            reply_markup=get_main_menu()
        )
        return
    
    await message.answer(
        "👋 Добро пожаловать! Давайте зарегистрируем вас.\n\n"
        "Шаг 1/5: Напишите ваше *имя* (только имя, без фамилии):",
        parse_mode="Markdown"
    )
    await state.set_state(Registration.first_name)


@router.message(Registration.first_name)
async def process_first_name(message: Message, state: FSMContext):
    if len(message.text) < 2 or len(message.text) > 50:
        await message.answer("❌ Имя должно быть от 2 до 50 символов. Попробуйте ещё раз:")
        return
    await state.update_data(first_name=message.text.strip())
    await message.answer("Шаг 2/5: Напишите вашу *фамилию*:", parse_mode="Markdown")
    await state.set_state(Registration.last_name)


@router.message(Registration.last_name)
async def process_last_name(message: Message, state: FSMContext):
    if len(message.text) < 2 or len(message.text) > 50:
        await message.answer("❌ Фамилия должна быть от 2 до 50 символов. Попробуйте ещё раз:")
        return
    await state.update_data(last_name=message.text.strip())
    await message.answer(
        "Шаг 3/5: Напишите *класс* (например: 10А, 9Б, 11В):",
        parse_mode="Markdown"
    )
    await state.set_state(Registration.class_number)


@router.message(Registration.class_number)
async def process_class(message: Message, state: FSMContext):
    class_input = message.text.strip().upper()
    if len(class_input) < 2 or len(class_input) > 5:
        await message.answer("❌ Некорректный класс. Примеры: 10А, 9Б. Попробуйте ещё раз:")
        return
    await state.update_data(class_number=class_input)
    await message.answer("Шаг 4/5: Напишите *название школы*:", parse_mode="Markdown")
    await state.set_state(Registration.school)


@router.message(Registration.school)
async def process_school(message: Message, state: FSMContext):
    if len(message.text) < 3:
        await message.answer("❌ Название школы слишком короткое. Попробуйте ещё раз:")
        return
    await state.update_data(school=message.text.strip())
    await message.answer(
        "Шаг 5/5: Отправьте *фотографию вашего лица* (аватарку), чтобы учитель мог вас узнать.\n\n"
        "📎 Прикрепите фото прямо в чат.",
        parse_mode="Markdown"
    )
    await state.set_state(Registration.avatar)


@router.message(Registration.avatar, F.photo)
async def process_avatar(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    
    # Скачиваем фото (берём самое большое разрешение)
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    
    # Генерируем уникальное имя файла
    import uuid
    filename = f"{message.from_user.id}_{uuid.uuid4().hex[:8]}.jpg"
    
    # Загружаем в Supabase Storage
    try:
        avatar_url = await upload_avatar(file_bytes.read(), filename)
    except Exception as e:
        await message.answer(f"❌ Ошибка загрузки фото: {e}\nПопробуйте отправить другое фото.")
        return
    
    # Сохраняем в БД
    student_data = {
        "telegram_id": message.from_user.id,
        "first_name": data["first_name"],
        "last_name": data["last_name"],
        "class_number": data["class_number"],
        "school": data["school"],
        "avatar_url": avatar_url
    }
    
    try:
        await create_student(student_data)
    except Exception as e:
        await message.answer(f"❌ Ошибка сохранения в базу данных: {e}")
        return
    
    await state.clear()
    await message.answer(
        f"✅ Регистрация завершена!\n\n"
        f"👤 {data['first_name']} {data['last_name']}\n"
        f"🏫 {data['school']}, {data['class_number']}\n\n"
        f"Теперь вы можете отправлять фото домашних заданий — они автоматически попадут к учителю.",
        reply_markup=get_main_menu()
    )


@router.message(Registration.avatar)
async def process_avatar_invalid(message: Message):
    await message.answer("❌ Пожалуйста, отправьте именно *фотографию*, а не текст или файл.", parse_mode="Markdown")
