import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from config import BOT_TOKEN, PROXY_URL
from handlers import start, registration, account, homework, chat
from services.dispatcher import dispatch_loop

# Настройка логирования
logging.basicConfig(level=logging.INFO)


async def main():
    # Настройка прокси (если задан в .env)
    if PROXY_URL:
        from aiohttp_socks import ProxyConnector
        connector = ProxyConnector.from_url(PROXY_URL)
        session = AiohttpSession(connector=connector)
        bot = Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        logging.info(f"Используется прокси: {PROXY_URL}")
    else:
        bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    dp = Dispatcher()

    # Подключаем роутеры (ПОРЯДОК ВАЖЕН: сценарии и кнопки выше, ловец текста — последним!)
    dp.include_router(start.router)
    dp.include_router(registration.router)
    dp.include_router(account.router)
    dp.include_router(homework.router)   # <-- кнопка «Отправить домашнее задание» здесь
    dp.include_router(chat.router)       # <-- ловец текста ВСЕГДА последний

    # Фоновая доставка сообщений сайта -> Telegram (раз в 15 сек)
    asyncio.create_task(dispatch_loop(bot))

    # Удаляем вебхук и запускаем polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
