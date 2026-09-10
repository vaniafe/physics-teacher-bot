import re
import uuid
import random

from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from services.supabase_client import (
    student_exists, create_student, upload_avatar, find_student_by_name, login_taken
)
from keyboards.main_menu import get_entry_keyboard, get_main_menu

router = Router()


class Registration(StatesGroup):
    first_name = State()
    last_name = State()
    class_number = State()
    school = State()
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

    # Если логин занят — добавляем номер: ivanov_i2, ivanov_i3 ...
    candidate = login
    n = 2
    while await login_taken(candidate):
        candidate = f"{login}{n}"
        n += 1
    return candidate


def generate_password() -> str:
    """Простой 6-значный пароль."""
    return str(random.randint(100000, 999999))


@router.message(F.text == "📝 Зарегистрироваться")
async def btn_register(message: Message, state: FSMContext):
    """Начало регистрации нового ученика."""
    await state.clear()

    if await student_exists(message.from_user.id):
        await message.answer("Вы уже зарегистрированы.", reply_markup=get_main_menu())
        return

    await message.answer(
        "Давайте зарегистрируем вас.\n\n"
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
