import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode

from config import BOT_TOKEN, PROXY_URL
from handlers import start, registration, account, homework, chat
from services.dispatcher import dispatch_loop

# Настройка логирования
logging.basicConfig(level=logging.INFO)


async def main():
    api_base = os.environ.get("TELEGRAM_API_BASE", "").strip()

    if PROXY_URL:
        from aiohttp_socks import ProxyConnector
        connector = ProxyConnector.from_url(PROXY_URL)
        session = AiohttpSession(connector=connector)
        bot = Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        logging.info(f"Используется прокси: {PROXY_URL}")
    elif api_base:
        # Альтернативный адрес Bot API (например, Cloudflare Worker-посредник)
        session = AiohttpSession(api=TelegramAPIServer.from_base(api_base))
        bot = Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        logging.info(f"Используется альтернативный API: {api_base}")
    else:
        bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    dp = Dispatcher()

    # Подключаем роутеры (порядок важен: ловец текста — последним)
    dp.include_router(start.router)
    dp.include_router(registration.router)
    dp.include_router(account.router)
    dp.include_router(homework.router)
    dp.include_router(chat.router)

    # Фоновая доставка сообщений сайта -> Telegram
    asyncio.create_task(dispatch_loop(bot))

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
