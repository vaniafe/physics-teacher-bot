from aiogram import Router, F
from aiogram.types import Message

from services.supabase_client import get_student, create_message

router = Router()


@router.message(F.text)
async def student_to_teacher(message: Message):
    """Любой текст от зарегистрированного ученика = сообщение учителю.

    Срабатывает только когда нет активного сценария (регистрация,
    вход, смена пароля и т.п.) — те роутеры подключены раньше.
    """
    student = await get_student(message.from_user.id)
    if not student:
        await message.answer("❌ Вы ещё не зарегистрированы. Нажмите /start.")
        return

    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        return  # команды и пустое — пропускаем

    await create_message({
        "student_id": student["id"],
        "sender": "student",
        "text": text,
        "tg_delivered": True,        # источник — сам Telegram
        "tg_message_id": message.message_id,
    })
    await message.answer("✅ Сообщение отправлено учителю.")
