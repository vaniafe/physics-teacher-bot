import asyncio
import uuid
from datetime import datetime, date, timedelta, timezone

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from services.supabase_client import (
    get_student, upload_homework_photo, create_submission, get_calendar_dates,
    upload_avatar, delete_avatar, update_student, count_session_photos
)
from keyboards.main_menu import get_main_menu

router = Router()


class HomeworkStates(StatesGroup):
    waiting_photo = State()      # ученик прикрепляет фото работы к выбранной дате
    waiting_avatar = State()     # ученик должен обновить фото профиля


def _fmt_date(iso_date: str) -> str:
    """'2026-09-15' -> '15.09.2026'"""
    try:
        return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return iso_date


def _homework_keyboard() -> InlineKeyboardMarkup:
    """Кнопки после загрузки фото."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить ещё фото", callback_data="hw:add")],
        [InlineKeyboardButton(text="✅ Завершить", callback_data="hw:finish")],
    ])


@router.message(F.text == "📸 Отправить домашнее задание")
async def start_homework(message: Message, state: FSMContext):
    """Начало сдачи работы. Если нужно обновить фото профиля — сначала оно."""

    # Проверяем, зарегистрирован ли ученик
    student = await get_student(message.from_user.id)
    if not student:
        await message.answer(
            "❌ Вы ещё не зарегистрированы!\n\n"
            "Нажмите /start, чтобы пройти регистрацию."
        )
        return

    # У учителя включён запрос на смену фото профиля
    if student.get("needs_avatar_update"):
        await state.set_state(HomeworkStates.waiting_avatar)
        await message.answer(
            "📸 Необходимо обновить фото профиля!\n\n"
            "Прикрепите новую фотографию вашего лица.\n"
            "После этого вы сможете отправлять домашние задания."
        )
        return

    # Даты из календаря, открытые учителем для этого класса
    dates = await get_calendar_dates(student["school"], student["class_number"])

    # Только диапазон: вчера — сегодня+5 дней
    today = date.today()
    lo = (today - timedelta(days=1)).isoformat()
    hi = (today + timedelta(days=5)).isoformat()
    allowed = [d for d in dates if lo <= d <= hi]

    if not allowed:
        await message.answer(
            "ℹ️ Сейчас нет доступных дат для сдачи домашнего задания.\n"
            "Даты открывает учитель в календаре на сайте.",
            reply_markup=get_main_menu()
        )
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📅 {_fmt_date(d)}", callback_data=f"cal:{d}")]
        for d in allowed
    ])
    await message.answer(
        "📅 Выберите дату сдачи домашнего задания:",
        reply_markup=keyboard
    )


@router.message(HomeworkStates.waiting_avatar, F.photo)
async def process_avatar_update(message: Message, state: FSMContext, bot: Bot):
    """Обновление фото профиля: удаляем старое фото, сохраняем новое,
    снимаем галочку needs_avatar_update."""
    student = await get_student(message.from_user.id)
    if not student:
        await state.clear()
        await message.answer("❌ Сначала зарегистрируйтесь: /start")
        return

    photo = message.photo[-1]
    try:
        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)
    except Exception as e:
        await message.answer(f"❌ Ошибка загрузки фото: {e}\nПопробуйте отправить ещё раз.")
        return

    filename = f"{message.from_user.id}_{uuid.uuid4().hex[:8]}.jpg"

    try:
        avatar_url = await upload_avatar(file_bytes.read(), filename)
    except Exception as e:
        await message.answer(f"❌ Ошибка загрузки фото: {e}\nПопробуйте отправить ещё раз.")
        return

    old_url = student.get("avatar_url")
    if old_url:
        try:
            await delete_avatar(old_url)
        except Exception:
            pass  # не критично

    try:
        await update_student(student["id"], {
            "avatar_url": avatar_url,
            "needs_avatar_update": False,
        })
    except Exception as e:
        await message.answer(f"❌ Ошибка сохранения: {e}")
        return

    await state.clear()
    await message.answer(
        "✅ Фото профиля обновлено!\n\n"
        "Теперь вы можете отправлять домашние задания.",
        reply_markup=get_main_menu()
    )


@router.message(HomeworkStates.waiting_avatar)
async def process_avatar_update_invalid(message: Message):
    await message.answer(
        "❌ Пожалуйста, отправьте именно *фотографию* (не текст или файл).",
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("cal:"))
async def choose_date(callback: CallbackQuery, state: FSMContext):
    """Ученик выбрал дату — ждём фото."""
    await callback.answer()

    student = await get_student(callback.from_user.id)
    if not student:
        await callback.message.answer("❌ Сначала зарегистрируйтесь: /start")
        return

    due_date = callback.data.split(":", 1)[1]

    await state.set_state(HomeworkStates.waiting_photo)
    await state.update_data(
        due_date=due_date,
        photos_count=0,
        keyboard_sent=False,
        session_start=datetime.now(timezone.utc).isoformat(),
    )

    await callback.message.answer(
        f"📅 Выбрана дата: <b>{_fmt_date(due_date)}</b>\n\n"
        "Теперь прикрепите фото домашнего задания (можно несколько сразу).",
        parse_mode="HTML"
    )


_photo_locks: dict = {}
_pending_kb: dict = {}


async def _send_hw_keyboard(bot: Bot, user_id: int, chat_id: int,
                            student_id, due_date: str, session_start: str,
                            state: FSMContext):
    """Показать кнопки «Добавить/Завершить» ОДИН РАЗ за сессию сдачи —
    после того, как обработан весь пакет фото (альбом приходит
    несколькими сообщениями; каждое новое фото отменяет таймер
    предыдущего, сработает только последний)."""
    try:
        await asyncio.sleep(2.5)
        count = await count_session_photos(student_id, due_date, session_start)
        await bot.send_message(
            chat_id,
            f"📎 Фото {count} сохранено на дату {_fmt_date(due_date)}.\n"
            "Можно прикрепить ещё фото или завершить.",
            reply_markup=_homework_keyboard(),
        )
        await state.update_data(keyboard_sent=True)
    except asyncio.CancelledError:
        pass  # пришло ещё фото из пакета — покажет следующий таймер
    finally:
        _pending_kb.pop(user_id, None)


@router.message(HomeworkStates.waiting_photo, F.photo)
async def process_photo(message: Message, state: FSMContext, bot: Bot):
    """Сохраняем фото работы с выбранной датой.

    Альбом из нескольких фото приходит пачкой сообщений — обрабатываем
    их строго по очереди (блокировка), чтобы счётчик не сбивался.
    """
    lock = _photo_locks.setdefault(message.from_user.id, asyncio.Lock())
    async with lock:
        await _process_photo_locked(message, state, bot)


async def _process_photo_locked(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    due_date = data.get("due_date")
    session_start = data.get("session_start")
    student = await get_student(message.from_user.id)

    if not student or not due_date:
        await state.clear()
        await message.answer("❌ Сессия сдачи истекла. Начните заново: «📸 Отправить домашнее задание».")
        return

    photo = message.photo[-1]
    try:
        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)
    except Exception as e:
        await message.answer(f"❌ Ошибка загрузки фото: {e}\nПопробуйте отправить ещё раз.")
        return

    filename = f"{student['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.jpg"

    # Автоповтор при временных сбоях сети (например, ошибка 520)
    photo_url = None
    last_err = None
    for _attempt in range(3):
        try:
            photo_url = await upload_homework_photo(file_bytes.read(), filename)
            break
        except Exception as e:
            last_err = e
            await asyncio.sleep(1.5)
    if not photo_url:
        await message.answer(f"❌ Ошибка загрузки фото: {last_err}\nПопробуйте отправить ещё раз.")
        return

    # Сохраняем работу: due_date — дата из календаря,
    # submitted_at проставится автоматически (время загрузки)
    try:
        await create_submission({
            "student_id": student["id"],
            "photo_url": photo_url,
            "status": "pending",
            "due_date": due_date,
        })
    except Exception as e:
        await message.answer(f"❌ Ошибка сохранения: {e}")
        return

    # Считаем фото текущей сессии по базе (корректно и при альбомах)
    count = await count_session_photos(student["id"], due_date, session_start)
    await state.update_data(photos_count=count)

    if data.get("keyboard_sent"):
        # Кнопки уже выданы в этой сессии сдачи — старые остаются рабочими,
        # новые не дублируем. Сообщаем только счёт.
        await message.answer(f"📎 Фото {count} сохранено на дату {_fmt_date(due_date)}.")
        return

    # Кнопки покажем один раз — когда весь пакет фото будет обработан
    old_task = _pending_kb.pop(message.from_user.id, None)
    if old_task:
        old_task.cancel()
    _pending_kb[message.from_user.id] = asyncio.create_task(
        _send_hw_keyboard(bot, message.from_user.id, message.chat.id,
                          student["id"], due_date, session_start, state)
    )


@router.callback_query(F.data == "hw:add")
async def add_more_photo(callback: CallbackQuery, state: FSMContext):
    """Кнопка «Добавить ещё фото»."""
    await callback.answer()
    current = await state.get_state()
    if current != HomeworkStates.waiting_photo:
        await callback.message.answer("Начните сдачу заново: «📸 Отправить домашнее задание».")
        return
    await callback.message.answer("📎 Прикрепите следующее фото.")


@router.callback_query(F.data == "hw:finish")
async def finish_homework(callback: CallbackQuery, state: FSMContext):
    """Кнопка «Завершить» — работа принята, возврат в главное меню.

    Считаем фото напрямую по базе за текущую сессию — точно,
    даже если ученик прикрепил альбом из нескольких фото.
    """
    await callback.answer()
    data = await state.get_data()
    due_date = data.get("due_date")
    session_start = data.get("session_start")
    student = await get_student(callback.from_user.id)

    old_task = _pending_kb.pop(callback.from_user.id, None)
    if old_task:
        old_task.cancel()

    if not due_date or not session_start or not student:
        await callback.message.answer(
            "Сессия сдачи уже завершена.\n"
            "Начните заново: «📸 Отправить домашнее задание»."
        )
        return

    count = await count_session_photos(student["id"], due_date, session_start)
    await state.clear()

    await callback.message.answer(
        f"✅ Работа принята! Всего фото: {count}.\n"
        "Учитель скоро проверит вашу работу.",
        reply_markup=get_main_menu()
    )


@router.message(F.photo)
async def stray_photo(message: Message, state: FSMContext):
    """Фото вне процесса сдачи."""
    if await state.get_state() is not None:
        return  # сообщение обработается другим обработчиком
    student = await get_student(message.from_user.id)
    if student:
        if student.get("needs_avatar_update"):
            await message.answer(
                "📸 Учитель запросил обновление фото профиля.\n"
                "Нажмите «📸 Отправить домашнее задание» и прикрепите своё фото."
            )
        else:
            await message.answer(
                "Чтобы сдать работу, нажмите «📸 Отправить домашнее задание» "
                "и выберите дату сдачи."
            )
    else:
        await message.answer("❌ Вы ещё не зарегистрированы. Нажмите /start.")
