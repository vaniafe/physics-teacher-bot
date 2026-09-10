from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def get_entry_keyboard() -> ReplyKeyboardMarkup:
    """Меню для НЕзарегистрированного пользователя."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Зарегистрироваться")],
            [KeyboardButton(text="✅ Я уже зарегистрирован")],
        ],
        resize_keyboard=True
    )


def get_main_menu() -> ReplyKeyboardMarkup:
    """Главное меню зарегистрированного ученика."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📸 Отправить домашнее задание")],
            [KeyboardButton(text="🔑 Мой логин для сайта")],
            [KeyboardButton(text="ℹ️ Помощь")],
        ],
        resize_keyboard=True
    )


def get_back_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с одной кнопкой «Назад» (для экранов ввода текста)."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Назад")]],
        resize_keyboard=True
    )


def get_profile_keyboard() -> InlineKeyboardMarkup:
    """Кнопки в разделе «Мой логин для сайта»."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить логин/пароль", callback_data="profile:change")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="nav:main")],
    ])


def get_help_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="nav:main")],
    ])
