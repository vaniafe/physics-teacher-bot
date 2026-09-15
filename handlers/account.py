import re

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from services.supabase_client import get_student, login_taken, update_student
from keyboards.main_menu import get_main_menu, get_back_keyboard, get_profile_keyboard, get_help_keyboard

router = Router()


class ProfileStates(StatesGroup):
    waiting_new_login = State()
    waiting_new_password = State()


async def _registered_student(message: Message):
    """Возвращает ученика или просит войти/зарегистрироваться."""
    student = await get_student(message.from_user.id)
    if not student:
        await message.answer(
            "❌ Вы ещё не зарегистрированы.\n\n"
            "Нажмите /start и выберите «📝 Зарегистрироваться»."
        )
    return student


@router.message(F.text == "🔑 Мой логин для сайта")
async def show_login(message: Message, state: FSMContext):
    """Показывает логин и пароль для входа на сайт."""
    await state.clear()
    student = await _registered_student(message)
    if not student:
        return

    login = student.get("login") or "— не задан —"
    password = student.get("password") or "— не задан —"

    await message.answer(
        f"🔑 Ваши данные для входа на сайт physfun.ru:\n\n"
        f"Логин: <code>{login}</code>\n"
        f"Пароль: <code>{password}</code>\n\n"
        f"⚠️ Никому не сообщайте эти данные!",
        reply_markup=get_profile_keyboard()
    )


@router.callback_query(F.data == "profile:change")
async def start_change(callback: CallbackQuery, state: FSMContext):
    """Начало смены логина/пароля."""
    await callback.answer()
    student = await get_student(callback.from_user.id)
    if not student:
        await callback.message.answer("❌ Сначала зарегистрируйтесь.")
        return

    await state.set_state(ProfileStates.waiting_new_login)
    await callback.message.answer(
        "Введите *новый логин* (латинские буквы, цифры и подчёркивание, от 3 символов).\n\n"
        f"Текущий логин: <code>{student.get('login') or '—'}</code>\n"
        "Можно ввести его же, если хотите оставить логин без изменений.",
        parse_mode="Markdown",
        reply_markup=get_back_keyboard()
    )


@router.message(ProfileStates.waiting_new_login)
async def process_new_login(message: Message, state: FSMContext):
    try:
        login = (message.text or "").strip()

        if not re.fullmatch(r"[A-Za-z0-9_]{3,32}", login):
            await message.answer(
                "❌ Логин может содержать только латинские буквы, цифры и подчёркивание "
                "(3–32 символа). Попробуйте ещё раз:"
            )
            return

        student = await get_student(message.from_user.id)
        if not student:
            await state.clear()
            await message.answer("❌ Профиль не найден. Нажмите /start.")
            return

        login_l = login.lower()

        # Старый логин можно оставить: проверяем занятость только если логин меняется
        if login_l != (student.get("login") or "").lower():
            if await login_taken(login_l, exclude_id=student["id"]):
                await message.answer("❌ Этот логин уже занят другим учеником. Придумайте другой:")
                return

        await state.update_data(new_login=login_l)
        await state.set_state(ProfileStates.waiting_new_password)
        await message.answer(
            f"Логин: <code>{login_l}</code>\n\nТеперь введите *новый пароль* (от 4 символов):",
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(ProfileStates.waiting_new_password)
async def process_new_password(message: Message, state: FSMContext):
    try:
        password = (message.text or "").strip()

        if len(password) < 4 or len(password) > 64:
            await message.answer("❌ Пароль должен быть от 4 до 64 символов. Попробуйте ещё раз:")
            return

        data = await state.get_data()
        student = await get_student(message.from_user.id)
        if not student:
            await state.clear()
            await message.answer("❌ Профиль не найден. Нажмите /start.")
            return

        await update_student(student["id"], {
            "login": data["new_login"],
            "password": password,
        })
        await state.clear()

        await message.answer(
            f"✅ Данные обновлены!\n\n"
            f"Логин: <code>{data['new_login']}</code>\n"
            f"Пароль: <code>{password}</code>",
            reply_markup=get_profile_keyboard()
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


HELP_TEXT = (
    "📖 <b>Справка по боту</b>\n\n"
    "<b>Кнопки меню:</b>\n"
    "📸 <b>Отправить домашнее задание</b> — выбрать дату из разрешённых учителем "
    "и прикрепить одно или несколько фото работы.\n"
    "🔑 <b>Мой логин для сайта</b> — показать логин и пароль для входа на сайт "
    "physfun.ru, а также изменить их.\n"
    "ℹ️ <b>Помощь</b> — эта справка.\n\n"
    "<b>Сообщения учителю:</b>\n"
    "Просто напишите любой текст в чат — учитель получит его на сайте и ответит там же.\n\n"
    "<b>Команды:</b>\n"
    "/start — главное меню\n"
    "/help — эта справка\n\n"
    "❓ По всем вопросам обращайтесь к учителю физики."
)


@router.message(F.text == "ℹ️ Помощь")
@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext):
    await state.clear()
    student = await _registered_student(message)
    if not student:
        return
    await message.answer(HELP_TEXT, reply_markup=get_help_keyboard())


@router.callback_query(F.data == "nav:main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    """Кнопка «Назад» из инлайн-разделов — в главное меню."""
    await callback.answer()
    await state.clear()
    await callback.message.answer("Главное меню:", reply_markup=get_main_menu())
