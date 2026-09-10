import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from config import BOT_TOKEN, PROXY_URL
from handlers import start, registration, account, homework

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
    
    # Подключаем роутеры (порядок важен!)
    dp.include_router(start.router)
    dp.include_router(registration.router)
    dp.include_router(account.router)
    dp.include_router(homework.router)
    
    # Удаляем вебхук и запускаем polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
