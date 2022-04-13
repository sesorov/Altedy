"""
User messages & commands processing
"""

import re

from aiogram import Bot, types
from aiogram.utils.exceptions import BadRequest, TelegramAPIError
from aiogram.types import ParseMode

from common.helper import UserStatus, VerifyString, get_md5
from configs.logger_conf import configure_logger
from database.database import UserDatabase, ClassroomDatabase
from infrastructure.keyboards.inline_keyboards import *
from infrastructure.keyboards.reply_keyboards import *
from infrastructure.keyboards.callbacks import *

LOGGER = configure_logger(__name__)


class Handler:
    """
    Main class for commands processing and interactions
    """

    def __init__(self, bot: Bot, db: UserDatabase, class_db: ClassroomDatabase, dispatcher):
        self.bot = bot
        self.db = db
        self.class_db = class_db
        self.last_msg_id = None  # Last BOT message ID (for updating)
        self._cached_msgs = []  # Bot & user interactions messages that should be deleted after certain step, e.g. email

        async def clean_chat(chat_id):
            """
            Delete messages in list
            :param chat_id:
            :param messages_ids:
            :return:
            """

            for msg in self._cached_msgs:
                await self.bot.delete_message(chat_id, msg)
            self._cached_msgs.clear()

        @dispatcher.message_handler(commands=["start"])
        async def start(message: types.Message):
            """
            Send a message when the command /start is issued.
            """
            user = message.from_user
            self.last_msg_id = (await self.bot.send_message(message.chat.id,
                                                            f"Hello, {user.username}! "
                                                            f"Please, complete registration for further actions.",
                                                            reply_markup=(await get_register_keyboard()))).message_id

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
            self._cached_msgs.append(message.message_id)  # Store user's text message for further chat cleanup
            try:
                chat_status = self.db.get_status(message.chat.id)

                # Registration-related statuses
                if chat_status == UserStatus.WAIT_EMAIL:
                    if re.fullmatch(VerifyString.EMAIL.value, message.text):
                        self.db.update(message.chat.id, {"email": message.text})

                        await clean_chat(message.chat.id)
                        self.db.set_status(message.chat.id, UserStatus.WAIT_FULL_NAME)

                        self._cached_msgs.append((await self.bot.send_message(
                            message.chat.id, "Now please enter your full name, e.g. John Doe or Ivanov Ivan Ivanovich")
                                                  ).message_id)
                    else:
                        self._cached_msgs.append((await self.bot.send_message(message.chat.id,
                                                  "Sorry, the email address you entered seems to be invalid. "  # noqa
                                                  "Please, check it and send one more time.")).message_id)  # noqa

                elif chat_status == UserStatus.WAIT_FULL_NAME:
                    if re.fullmatch(VerifyString.FULL_NAME.value, message.text):
                        self.db.update(message.chat.id, {"full_name": message.text})
                        await clean_chat(message.chat.id)

                        if self.db.get_type(message.chat.id) == "student":
                            self.db.set_status(message.chat.id, UserStatus.MAIN_MENU)
                            await clean_chat(message.chat.id)

                            self._cached_msgs.append((await self.bot.send_message(
                                message.chat.id, "Thanks, now we're ready to go!",
                                reply_markup=await get_main_menu_markup("student"))).message_id)
                        else:  # teacher
                            await ask_classroom_name(chat_id=message.chat.id)
                    else:
                        self._cached_msgs.append((await self.bot.send_message(message.chat.id,
                                                          "Sorry, the name you entered seems to be invalid."  # noqa
                                                          "Write is as in example below:")).message_id)  # noqa
                        self._cached_msgs.append((await self.bot.send_message(message.chat.id, "Ivanov Ivan Ivanovich")
                                                  ).message_id)

                elif chat_status == UserStatus.WAIT_CLASSROOM_NAME:
                    # Generate MD5 for group using teacher's ID
                    hash_id = get_md5(f"{message.chat.id}-{message.text}")
                    # Add a record to classrooms database
                    self.class_db.add_raw(classroom_id=hash_id, teacher_id=message.chat.id,
                                          additional={"name": message.text})
                    self._cached_msgs.append((await self.bot.send_message(
                        message.chat.id,
                        f"Classroom {message.text} created successfully! "
                        f"Send its ID (message below) to your students.")).message_id)
                    self._cached_msgs.append((await self.bot.send_message(message.chat.id,
                                                        f"Click on ID to copy: `{hash_id}`",    # noqa
                                                        parse_mode=ParseMode.MARKDOWN,
                                                        reply_markup=await get_main_menu_markup("teacher"))
                                              ).message_id)

                elif chat_status == UserStatus.MAIN_MENU:

                    # Registration
                    if message.text == "Register":
                        # Begin registration (exists)
                        pass

                    # Teacher-related
                    elif message.text == "Create group":
                        # Run creating algorithm (exists)
                        pass
                    elif message.text == "Managed groups":
                        # Show list of inline buttons representing groups
                        pass

                    # Student-related
                    elif message.text == "Add group":
                        await clean_chat(message.chat.id)
                        self.db.set_status(message.chat.id, UserStatus.STUDENT_ADD_GROUP)

                        self._cached_msgs.append((await self.bot.send_message(
                            message.chat.id, "Please, send me group ID. "
                                             "If you don't have one, ask your teacher or classmates.")).message_id)
                    elif message.text == "My groups":
                        # Show list of inline buttons representing groups
                        pass
                    elif message.text == "My marks":
                        # Send message with avg marks for each group of current student and a file with marks
                        pass
                    elif message.text == "Deadlines":
                        # Show list of deadlines for every active task in every group
                        pass

                # ============ STUDENT ACTIONS ============
                elif chat_status == UserStatus.STUDENT_ADD_GROUP:
                    if self.class_db.add_student(message.chat.id, message.text):
                        self.db.set_status(message.chat.id, UserStatus.MAIN_MENU)
                        await clean_chat(message.chat.id)

                        group_name = self.class_db.get_info(message.text)["name"]
                        self._cached_msgs.append((await self.bot.send_message(
                            message.chat.id, f"Congratulations, you are now a member of {group_name}!",
                            reply_markup=await get_main_menu_markup("student"))).message_id)
            except Exception as exc:
                await self.bot.send_message(message.chat.id, "Sorry, I didn't get you.",
                                            reply_markup=await get_main_menu_markup(self.db.get_type(message.chat.id)))
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
            await self.bot.edit_message_text("Choose working mode:", callback_query.from_user.id, self.last_msg_id,
                                             reply_markup=await get_student_teacher_keyboard())
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
            await self.bot.edit_message_text("Would you like to share your email to receive notifications?",
                                             callback_query.from_user.id, self.last_msg_id,
                                             reply_markup=await get_ask_email_keyboard())
            await self.bot.answer_callback_query(callback_query.id)

        @dispatcher.callback_query_handler(lambda callback: callback.data == CALLBACK_EMAIL_TRUE)
        async def reg_ask_email(callback_query: types.CallbackQuery):
            """
            Ask for email address (if user decided to share email before)
            Produces simple message without keyboard
            :param callback_query:
            :return: None
            """

            self._cached_msgs.append(self.last_msg_id)  # since next msgs are text from user, we no longer need this one
            self._cached_msgs.append((await self.bot.send_message(
                callback_query.from_user.id, "Please, write your email as sample@address.com")).message_id)

        # ================ REGISTRATION END ================

        # ================ CLASSROOM CREATE BEGIN ================
        # Methods below are used to maintain registration process and steps.

        @dispatcher.callback_query_handler(lambda callback: callback.data == CALLBACK_CREATE_CLASSROOM)
        async def ask_classroom_name(callback_query: types.CallbackQuery = None, chat_id = None):
            """
            Ask for classroom name
            Produces simple message without keyboard
            :param chat_id: Pass if called from code
            :param callback_query: Pass if called from keyboard
            :return:
            """

            _id = chat_id if chat_id else callback_query.from_user.id
            self.db.set_status(_id, UserStatus.WAIT_CLASSROOM_NAME)
            self._cached_msgs.append((await self.bot.send_message(
                            _id, "Please, enter the name of your first classroom. "
                                 "You will be able to create more later. "
                                 "The recommended format is like: Data Management 19BI-3")).message_id)
            if not chat_id:
                await self.bot.answer_callback_query(callback_query.id)

        # ================ CLASSROOM CREATE END ================
