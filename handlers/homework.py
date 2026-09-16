import asyncio
import re
import uuid
import random

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from services.supabase_client import (
    student_exists, create_student, upload_avatar, find_student_by_name, login_taken
)
from keyboards.main_menu import get_entry_keyboard, get_main_menu

router = Router()

# Школы и классы
SCHOOLS = ["СОШ №1 г. Голицыно", "Маловяземская СОШ"]
SCHOOL_CLASSES = {
    "СОШ №1 г. Голицыно": ["10", "11"],
    "Маловяземская СОШ": ["9А", "9Б", "9В", "10", "11"],
}


class Registration(StatesGroup):
    school = State()        # выбор школы и класса (кнопками)
    first_name = State()
    last_name = State()
    avatar = State()


# Транслитерация русских букв в латиницу
TRANSLIT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
}


def translit(text: str) -> str:
    return ''.join(TRANSLIT.get(ch, ch) for ch in text.lower())


async def generate_login(first_name: str, last_name: str) -> str:
    """Логин = фамилия латиницей + '_' + первая буква имени. Пример: ivanov_i"""
    base = translit(last_name)
    base = re.sub(r'[^a-z0-9]', '', base)
    letter = translit(first_name)[:1]
    login = f"{base}_{letter}"

    candidate = login
    n = 2
    while await login_taken(candidate):
        candidate = f"{login}{n}"
        n += 1
    return candidate


def generate_password() -> str:
    """Простой 6-значный пароль."""
    return str(random.randint(100000, 999999))


def _school_keyboard() -> InlineKeyboardMarkup:
    """Кнопки выбора школы."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=school, callback_data=f"regschool:{i}")]
        for i, school in enumerate(SCHOOLS)
    ])


def _class_keyboard(school: str) -> InlineKeyboardMarkup:
    """Кнопки выбора класса для выбранной школы."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{cls} класс", callback_data=f"regcls:{cls}")]
        for cls in SCHOOL_CLASSES.get(school, [])
    ])


@router.message(F.text == "📝 Зарегистрироваться")
async def btn_register(message: Message, state: FSMContext):
    """Начало регистрации: выбор школы."""
    await state.clear()

    if await student_exists(message.from_user.id):
        await message.answer("Вы уже зарегистрированы.", reply_markup=get_main_menu())
        return

    await state.set_state(Registration.school)
    await message.answer(
        "Давайте зарегистрируем вас.\n\n"
        "Шаг 1/4: Выберите вашу *школу*:",
        parse_mode="Markdown",
        reply_markup=_school_keyboard()
    )


@router.callback_query(F.data.startswith("regschool:"))
async def process_school_choice(callback: CallbackQuery, state: FSMContext):
    """Ученик выбрал школу — предлагаем классы этой школы."""
    await callback.answer()

    current = await state.get_state()
    if current != Registration.school.state:
        return  # старые кнопки игнорируем

    school = SCHOOLS[int(callback.data.split(":")[1])]
    await state.update_data(school=school)

    await callback.message.answer(
        f"🏫 {school}\n\n"
        "Шаг 2/4: Выберите ваш *класс*:",
        parse_mode="Markdown",
        reply_markup=_class_keyboard(school)
    )


@router.callback_query(F.data.startswith("regcls:"))
async def process_class_choice(callback: CallbackQuery, state: FSMContext):
    """Ученик выбрал класс — просим имя."""
    await callback.answer()

    current = await state.get_state()
    if current != Registration.school.state:
        return  # старые кнопки игнорируем

    class_number = callback.data.split(":", 1)[1]
    await state.update_data(class_number=class_number)
    await state.set_state(Registration.first_name)

    await callback.message.answer(
        f"📚 {class_number} класс\n\n"
        "Шаг 3/4: Напишите ваше *имя* (только имя, без фамилии):",
        parse_mode="Markdown"
    )


@router.message(Registration.first_name)
async def process_first_name(message: Message, state: FSMContext):
    if not message.text or len(message.text) < 2 or len(message.text) > 50:
        await message.answer("❌ Имя должно быть от 2 до 50 символов. Попробуйте ещё раз:")
        return
    await state.update_data(first_name=message.text.strip())
    await message.answer("Шаг 4/4: Напишите вашу *фамилию*:", parse_mode="Markdown")
    await state.set_state(Registration.last_name)


@router.message(Registration.last_name)
async def process_last_name(message: Message, state: FSMContext):
    if not message.text or len(message.text) < 2 or len(message.text) > 50:
        await message.answer("❌ Фамилия должна быть от 2 до 50 символов. Попробуйте ещё раз:")
        return

    last_name = message.text.strip()
    data = await state.get_data()

    # Проверка на дубликат имени и фамилии (без учёта регистра)
    existing = await find_student_by_name(data["first_name"], last_name)
    if existing:
        await state.clear()
        await message.answer(
            "❌ Пользователь с таким именем уже зарегистрирован.\n\n"
            "Если это вы — нажмите «✅ Я уже зарегистрирован» "
            "и войдите по логину и паролю.",
            reply_markup=get_entry_keyboard()
        )
        return

    await state.update_data(last_name=last_name)
    await message.answer(
        "Отлично! Последний шаг: отправьте *фотографию вашего лица* (аватарку), "
        "чтобы учитель мог вас узнать.\n\n"
        "📎 Прикрепите фото прямо в чат (только одно фото).",
        parse_mode="Markdown"
    )
    await state.set_state(Registration.avatar)


_reg_locks: dict = {}


@router.message(Registration.avatar, F.photo)
async def process_avatar(message: Message, state: FSMContext, bot: Bot):
    """Фото профиля. Если прислали несколько фото пакетом —
    используем только ПЕРВОЕ, остальные игнорируем."""
    lock = _reg_locks.setdefault(message.from_user.id, asyncio.Lock())
    async with lock:
        await _process_avatar_locked(message, state, bot)


async def _process_avatar_locked(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()

    # Регистрация уже завершена по первому фото пакета — остальные пропускаем
    if not data.get("last_name"):
        return

    # Генерируем логин и пароль для сайта
    login = await generate_login(data["first_name"], data["last_name"])
    password = generate_password()

    # Скачиваем фото (берём самое большое разрешение)
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)

    filename = f"{message.from_user.id}_{uuid.uuid4().hex[:8]}.jpg"

    try:
        avatar_url = await upload_avatar(file_bytes.read(), filename)
    except Exception as e:
        await message.answer(f"❌ Ошибка загрузки фото: {e}\nПопробуйте отправить другое фото.")
        return

    student_data = {
        "telegram_id": message.from_user.id,
        "first_name": data["first_name"],
        "last_name": data["last_name"],
        "class_number": data["class_number"],
        "school": data["school"],
        "avatar_url": avatar_url,
        "tg_username": message.from_user.username,
        "login": login,
        "password": password,
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
        f"🔑 Ваши данные для входа на сайт physfun.ru:\n"
        f"Логин: <code>{login}</code>\n"
        f"Пароль: <code>{password}</code>\n\n"
        f"Сохраните их! Посмотреть снова можно в разделе «🔑 Мой логин для сайта».",
        reply_markup=get_main_menu()
    )


@router.message(Registration.avatar)
async def process_avatar_invalid(message: Message):
    await message.answer("❌ Пожалуйста, отправьте именно *фотографию*, а не текст или файл.", parse_mode="Markdown")
