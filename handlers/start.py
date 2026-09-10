from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from services.supabase_client import student_exists, get_student_by_login, update_student
from keyboards.main_menu import get_entry_keyboard, get_main_menu, get_back_keyboard

router = Router()


class AuthStates(StatesGroup):
    waiting_login = State()
    waiting_password = State()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Команда /start: главное меню или экран входа."""
    await state.clear()

    if await student_exists(message.from_user.id):
        await message.answer(
            f"Привет, {message.from_user.first_name}! 👋\n\n"
            "Выберите действие в меню ниже:",
            reply_markup=get_main_menu()
        )
        return

    await message.answer(
        "👋 Добро пожаловать в бота для сдачи домашних заданий по физике!\n\n"
        "Выберите действие:",
        reply_markup=get_entry_keyboard()
    )


@router.message(F.text == "⬅️ Назад")
async def btn_back(message: Message, state: FSMContext):
    """Глобальная кнопка «Назад» — выход из любого экрана в меню."""
    await state.clear()
    if await student_exists(message.from_user.id):
        await message.answer("Главное меню:", reply_markup=get_main_menu())
    else:
        await message.answer("Выберите действие:", reply_markup=get_entry_keyboard())


@router.message(F.text == "✅ Я уже зарегистрирован")
async def btn_already_registered(message: Message, state: FSMContext):
    """Вход по логину и паролю (например, после смены телефона/аккаунта)."""
    await state.clear()

    if await student_exists(message.from_user.id):
        await message.answer("Этот Telegram-аккаунт уже привязан к ученику.", reply_markup=get_main_menu())
        return

    await state.set_state(AuthStates.waiting_login)
    await message.answer(
        "Введите ваш *логин* для сайта:",
        parse_mode="Markdown",
        reply_markup=get_back_keyboard()
    )


@router.message(AuthStates.waiting_login)
async def process_auth_login(message: Message, state: FSMContext):
    login = (message.text or "").strip()
    if len(login) < 3:
        await message.answer("❌ Логин слишком короткий. Попробуйте ещё раз:")
        return
    await state.update_data(login=login)
    await state.set_state(AuthStates.waiting_password)
    await message.answer("Введите ваш *пароль*:", parse_mode="Markdown")


@router.message(AuthStates.waiting_password)
async def process_auth_password(message: Message, state: FSMContext):
    password = (message.text or "").strip()
    data = await state.get_data()
    login = data.get("login", "")

    student = await get_student_by_login(login)

    if student and student.get("password") and student["password"] == password:
        # Привязываем текущий Telegram-аккаунт к ученику
        await update_student(student["id"], {
            "telegram_id": message.from_user.id,
            "tg_username": message.from_user.username,
        })
        await state.clear()
        await message.answer(
            f"✅ Вход выполнен!\n\n"
            f"👤 {student['first_name']} {student['last_name']}, "
            f"{student['class_number']} класс, {student['school']}\n\n"
            f"Теперь вы можете отправлять домашние задания.",
            reply_markup=get_main_menu()
        )
    else:
        await state.clear()
        await message.answer(
            "❌ Пользователь не найден. Проверьте логин и пароль.",
            reply_markup=get_entry_keyboard()
        )
