"""
Main Altedy Bot script
"""
import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.contrib.middlewares.logging import LoggingMiddleware

from configs.logger_conf import configure_logger
from configs.bot_conf import BotConfig
from database.database import UserDatabase
from infrastructure.message_handler import Handler

LOGGER = configure_logger(__name__)


async def init_bot(dispatcher, bot):
    """
    Async function to call init_db and init translator and handler
    """

    db = UserDatabase()
    await asyncio.sleep(3)
    # Language translator
    #dispatcher_.middleware.setup(LanguageMiddleware("bot", path=Path(__file__).parents[2] / "locales", mongo=mongo_))

    # Message handler
    Handler(bot, db, dispatcher)

    #dispatcher_.middleware.setup(LoggingMiddleware(logger=logger))
    #dispatcher_.middleware.setup(ThrottlingMiddleware())

if __name__ == "__main__":
    LOGGER.info("Starting bot")

    token = BotConfig().properties["BOT"]["TOKEN"]
    bot = Bot(token=token)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    dispatcher = Dispatcher(bot, storage=MemoryStorage(), loop=loop)
    dispatcher.loop.create_task(init_bot(dispatcher, bot))
    executor.start_polling(dispatcher, skip_updates=True)
