"""
User messages & commands processing
"""

import re

from aiogram import Bot, types
from aiogram.utils.exceptions import BadRequest, TelegramAPIError

from common.helper import UserStatus, VerifyString
from configs.logger_conf import configure_logger
from database.database import UserDatabase
from infrastructure.keyboards.inline_keyboards import *
from infrastructure.keyboards.reply_keyboards import *
from infrastructure.keyboards.callbacks import *

LOGGER = configure_logger(__name__)


class Handler:
    """
    Main class for commands processing and interactions
    """

    def __init__(self, bot: Bot, db: UserDatabase, dispatcher):
        self.bot = bot
        self.db = db

        @dispatcher.message_handler(commands=["start"])
        async def start(message: types.Message):
            """
            Send a message when the command /start is issued.
            """
            user = message.from_user
            await self.bot.send_message(message.chat.id, f"Hello, {user.username}! "
                                                         f"Please, complete registration for further actions.",
                                        reply_markup=(await get_register_keyboard()))

        @dispatcher.message_handler(commands=["help"])
        async def chat_help(message: types.Message):
            """
            Send a message when the command /help is issued.
            """
            await self.bot.send_message(message.chat.id, "", reply_markup=(await get_help_keyboard()))

        @dispatcher.errors_handler()
        def error(update: types.Update, exception: TelegramAPIError):
            """
            Log errors caused by Update.
            """
            LOGGER.error(f"Update {update} caused error {exception}.")

        @dispatcher.message_handler(content_types=["text"])
        async def text_handler(message: types.Message):
            """
            Handle all user's text data and perform actions according to current user's status
            """
            try:
                chat_status = await self.db.get_status(message.chat.id)

                if chat_status == UserStatus.WAIT_EMAIL:
                    if re.fullmatch(VerifyString.EMAIL.value, message.text):
                        self.db.update(message.chat.id, {"email": message.text})
                        self.db.set_status(message.chat.id, UserStatus.WAIT_FULL_NAME)
                        await self.bot.send_message(message.chat.id,
                                                    "Now please enter your full name, e.g. John Doe or Ivanov Ivan Ivanovich")
                        await self.bot.answer_callback_query(message.chat.id)
                    else:
                        await self.bot.send_message(message.chat.id,
                                                    "Sorry, the email address you entered seems to be invalid. "
                                                    "Please, check it and send one more time.")

                if chat_status == UserStatus.WAIT_FULL_NAME:
                    if re.fullmatch(VerifyString.FULL_NAME.value, message.text):
                        self.db.update(message.chat.id, {"full_name": message.text})
                        if self.db.get_type(message.chat.id) == "student":
                            self.db.set_status(message.chat.id, UserStatus.WAIT_CLASSROOM_ID)
                        else:  # teacher
                            pass
                    else:
                        await self.bot.send_message(message.chat.id,
                                                    "Sorry, the name you entered seems to be invalid."
                                                    "Write is as in example below:")
                        await self.bot.send_message(message.chat.id, "Ivanov Ivan Ivanovich")
            except Exception as exc:
                await self.bot.send_message(message.chat.id, no_db_message())
                LOGGER.warning(exc)
                return

        # ================ REGISTRATION BEGIN ================
        # Methods below are used to maintain registration process and steps.

        @dispatcher.callback_query_handler(lambda callback: callback.data == CALLBACK_REGISTER_1)
        async def reg_begin_registration(callback_query: types.CallbackQuery):
            """
            First time registration
            :param callback_query:
            :return: None
            """
            self.db.add_raw(callback_query.from_user.id)
            msg = await self.bot.send_message(callback_query.from_user.id, "Choose working mode:",
                                              reply_markup=(await get_student_teacher_keyboard()))
            await self.bot.answer_callback_query(callback_query.id)

        @dispatcher.callback_query_handler(lambda callback: callback.data in [CALLBACK_IS_STUDENT,
                                                                              CALLBACK_IS_TEACHER])
        async def reg_ask_email_permission(callback_query: types.CallbackQuery):
            """
            Whether to use email or not (yes/no)
            :param callback_query:
            :return: None
            """
            self.db.update(callback_query.from_user.id, {"type": callback_query.data})
            self.db.set_status(callback_query.from_user.id, UserStatus.WAIT_EMAIL)
            await self.bot.send_message(callback_query.from_user.id,
                                        "Would you like to share your email to receive notifications?",
                                        reply_markup=(await get_ask_email_keyboard()))
            await self.bot.answer_callback_query(callback_query.id)

        @dispatcher.callback_query_handler(lambda callback: callback.data == CALLBACK_EMAIL_TRUE)
        async def reg_ask_email(callback_query: types.CallbackQuery):
            """
            Ask for email address (if user decided to share email before)
            :param callback_query:
            :return: None
            """

            await self.bot.send_message(callback_query.from_user.id, "Please, write your email as sample@address.com")

        # ================ REGISTRATION END ================

        # ================ CLASSROOM CREATE BEGIN ================
        # Methods below are used to maintain registration process and steps.

        # ================ CLASSROOM CREATE END ================
