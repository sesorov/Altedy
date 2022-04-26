"""
Main Altedy Bot script
"""

import asyncio

from aiogram import Bot, Dispatcher, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from configs.logger_conf import configure_logger
from configs.bot_conf import BotConfig
from database.database import UserDatabase, ClassroomDatabase, DeadlineDatabase
from infrastructure.message_handler import Handler
from infrastructure.task import check_deadlines

LOGGER = configure_logger(__name__)


async def init_bot(dispatcher, bot):
    """
    Async function to call init_db and init translator and handler
    """

    db = UserDatabase()
    class_db = ClassroomDatabase()
    deadlines_db = DeadlineDatabase()
    await asyncio.sleep(3)

    Handler(bot, db, class_db, deadlines_db, dispatcher)
    check_deadlines(bot)

if __name__ == "__main__":
    LOGGER.info("Starting bot")

    token = BotConfig().properties["BOT"]["TOKEN"]
    bot = Bot(token=token)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    dispatcher = Dispatcher(bot, storage=MemoryStorage(), loop=loop)
    dispatcher.loop.create_task(init_bot(dispatcher, bot))
    executor.start_polling(dispatcher, skip_updates=True)
