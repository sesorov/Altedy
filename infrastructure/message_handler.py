"""
User messages & commands processing
"""

# pylint: disable = fixme, too-few-public-methods, wildcard-import, unused-wildcard-import, too-many-locals, too-many-statements, logging-fstring-interpolation # noqa

import re
import os

from pathlib import Path

from aiogram import Bot, types
from aiogram.utils.exceptions import TelegramAPIError
from aiogram.types import ParseMode
from aiogram.dispatcher import FSMContext
from dateutil.parser import parse  # type: ignore

from common.helper import UserStatus, VerifyString, get_md5, get_temp_dir
from configs.logger_conf import configure_logger
from database.database import UserDatabase, ClassroomDatabase, DeadlineDatabase
from infrastructure.keyboards.inline_keyboards import *
from infrastructure.keyboards.reply_keyboards import *
from infrastructure.keyboards.callbacks import *
from infrastructure.task import Task

LOGGER = configure_logger(__name__)


class Handler:
    """
    Main class for commands processing and interactions
    """

    def __init__(self, bot: Bot, db: UserDatabase,  # pylint: disable=invalid-name, too-many-arguments
                 class_db: ClassroomDatabase, deadlines_db: DeadlineDatabase, dispatcher):
        self.bot = bot

        self.db = db  # pylint: disable=invalid-name
        self.class_db = class_db
        self.deadlines_db = deadlines_db

        self.last_msg_id = None  # Last BOT message ID (for updating)
        self._cached_msgs = []  # type: ignore # Bot & user interactions messages that should be deleted after certain step # noqa
        self._user_type = None  # student or teacher (to avoid numerous requests to DB)

        async def clean_chat(chat_id):
            """
            Delete messages in list
            :param chat_id:
            :return:
            """

            for msg in self._cached_msgs:
                await self.bot.delete_message(chat_id, msg)
            self._cached_msgs.clear()

        # region /commands

        @dispatcher.message_handler(commands=["start"])
        async def start(message: types.Message):
            """
            Send a message when the command /start is issued.
            """
            user = message.from_user
            self.last_msg_id = (await self.bot.send_message(message.chat.id,
                                                            f"Hello, {user.username}! "
                                                            f"Please, complete registration for further actions.",
                                                            reply_markup=await get_register_keyboard())).message_id

        @dispatcher.message_handler(commands=["help"])
        async def chat_help(message: types.Message):
            """
            Send a message when the command /help is issued.
            """
            await self.bot.send_message(message.chat.id, "", reply_markup=(await get_help_keyboard()))

        # endregion

        @dispatcher.errors_handler()
        def error(update: types.Update, exception: TelegramAPIError):
            """
            Log errors caused by Update.
            """
            LOGGER.error(f"Update {update} caused error {exception}.")

        # region Registration
        # Methods below are used to maintain registration process and steps.

        @dispatcher.message_handler(content_types=["text"], state=UserStatus.WAIT_EMAIL)
        async def email_handler(message: types.Message):
            """
            Handle user's email

            :param state:
            :param message:
            :return:
            """

            self._cached_msgs.append(message.message_id)

            if re.fullmatch(VerifyString.EMAIL.value, message.text):
                self.db.update(message.chat.id, {"email": message.text})

                await clean_chat(message.chat.id)

                self._cached_msgs.append((await self.bot.send_message(
                    message.chat.id, "Now please enter your full name, e.g. John Doe or Ivanov Ivan Ivanovich")
                                          ).message_id)

                await UserStatus.WAIT_FULL_NAME.set()

            else:
                self._cached_msgs.append((await self.bot.send_message(message.chat.id,
                                                                      "Sorry, the email address you entered seems to be invalid. "  # noqa
                                                                      "Please, check it and send one more time.")).message_id)  # noqa

        @dispatcher.message_handler(content_types=["text"], state=UserStatus.WAIT_FULL_NAME)
        async def name_handler(message: types.Message):
            """
            Handle users's name

            :param message:
            :param state:
            :return:
            """

            self._cached_msgs.append(message.message_id)

            if re.fullmatch(VerifyString.FULL_NAME.value, message.text):
                self.db.update(message.chat.id, {"full_name": message.text})
                await clean_chat(message.chat.id)

                if self._user_type == "student":
                    await clean_chat(message.chat.id)

                    self._cached_msgs.append((await self.bot.send_message(
                        message.chat.id, "Thanks, now we're ready to go!",
                        reply_markup=await get_main_menu_markup("student"))).message_id)
                    await UserStatus.MAIN_MENU.set()
                else:  # teacher
                    await ask_classroom_name(chat_id=message.chat.id)
            else:
                self._cached_msgs.append((await self.bot.send_message(message.chat.id,
                                                                      "Sorry, the name you entered seems to be invalid."  # noqa
                                                                      "Write is as in example below:")).message_id)  # noqa
                self._cached_msgs.append((await self.bot.send_message(message.chat.id, "Ivanov Ivan Ivanovich")
                                          ).message_id)

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

        @dispatcher.callback_query_handler(lambda callback: callback.data == CALLBACK_SIGNIN)
        async def reg_sign_in(callback_query: types.CallbackQuery):
            """
            Existing user login
            :param callback_query:
            :return: None
            """
            self._cached_msgs.append(self.last_msg_id)
            await clean_chat(callback_query.from_user.id)
            if self.db.exists(callback_query.from_user.id):
                self._user_type = self.db.get_type(callback_query.from_user.id)
                self._cached_msgs.append((await self.bot.send_message(
                    callback_query.from_user.id, f"Welcome back, {callback_query.from_user.username}!",
                    reply_markup=await get_main_menu_markup(self._user_type))).message_id)
                await UserStatus.MAIN_MENU.set()
            else:
                self.last_msg_id = (await self.bot.send_message(
                    callback_query.from_user.id, "Sorry, you're not registered yet.",
                    reply_markup=await get_register_keyboard())).message_id
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
            self._user_type = callback_query.data
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
            await UserStatus.WAIT_EMAIL.set()

        # endregion

        # region Classroom (creating)
        # Methods below are used to maintain classroom creation process

        @dispatcher.message_handler(content_types=["text"], state=UserStatus.WAIT_CLASSROOM_NAME)
        async def classroom_name_handler(message: types.Message):
            """
            Handle classroom's name (for teacher)
            :param message:
            :param state:
            :return:
            """

            self._cached_msgs.append(message.message_id)

            # Generate MD5 for group using teacher's ID
            hash_id = get_md5(f"{message.chat.id}-{message.text}")
            # Add a record to classrooms database
            self.class_db.add_raw(classroom_id=hash_id, teacher_id=message.chat.id,
                                  additional={"name": message.text})
            # Add classroom ID to managed classrooms list in user DB for quick access
            self.db.array_append({"user_id": message.chat.id}, "managed_classrooms", hash_id, collection_name=None)
            self._cached_msgs.append((await self.bot.send_message(
                message.chat.id,
                f"Classroom {message.text} created successfully! "
                f"Send its ID (message below) to your students.")).message_id)
            self._cached_msgs.append((await self.bot.send_message(message.chat.id,
                                                                  f"Click on ID to copy: `{hash_id}`",  # noqa
                                                                  parse_mode=ParseMode.MARKDOWN,
                                                                  reply_markup=await get_main_menu_markup("teacher"))
                                      ).message_id)
            await UserStatus.MAIN_MENU.set()

        @dispatcher.callback_query_handler(lambda callback: callback.data == CALLBACK_CREATE_CLASSROOM)
        async def ask_classroom_name(callback_query: types.CallbackQuery = None, chat_id=None):
            """
            Ask for classroom name
            Produces simple message without keyboard
            :param chat_id: Pass if called from code
            :param callback_query: Pass if called from keyboard
            :return:
            """

            _id = chat_id if chat_id else callback_query.from_user.id  # type: ignore
            self._cached_msgs.append((await self.bot.send_message(
                _id, "Please, enter the name of your first classroom. "
                     "You will be able to create more later. "
                     "The recommended format is like: Data Management 19BI-3")).message_id)
            await UserStatus.WAIT_CLASSROOM_NAME.set()
            if not chat_id:
                await self.bot.answer_callback_query(callback_query.id)  # type: ignore

        # endregion

        # region Student: main actions

        @dispatcher.message_handler(lambda message: message.text in ["Add group"], state=UserStatus.all_states)
        async def student_add_group(message: types.Message):
            """
            Begin of group adding algorythm
            :param message:
            :return:
            """

            await clean_chat(message.chat.id)

            self._cached_msgs.append((await self.bot.send_message(
                message.chat.id, "Please, send me group ID. "
                                 "If you don't have one, ask your teacher or classmates.")).message_id)
            await UserStatus.STUDENT_ADD_GROUP.set()

        @dispatcher.message_handler(content_types=["text"], state=UserStatus.STUDENT_ADD_GROUP)
        async def classroom_id_handler(message: types.Message):
            """
            Handle student-provided classroom_id
            :param message:
            :return:
            """
            if self.class_db.add_student(message.chat.id, message.text):
                await clean_chat(message.chat.id)

                group_info = self.class_db.get_info(message.text)
                group_name = group_info["name"]
                self.db.array_append({"user_id": message.chat.id}, "classrooms",
                                     group_info["classroom_id"], collection_name=None)
                self._cached_msgs.append((await self.bot.send_message(
                    message.chat.id, f"Congratulations, you are now a member of {group_name}!",
                    reply_markup=await get_main_menu_markup("student"))).message_id)
                await UserStatus.MAIN_MENU.set()
            else:
                self._cached_msgs.append((await self.bot.send_message(
                    message.chat.id, "Sorry, couldn't add you to the group.\n"
                                     "Please, check the ID you've entered or list of your classrooms "
                                     "(perhaps you are already a member of this group).")).message_id)

        @dispatcher.message_handler(lambda message: message.text in ["My groups"], state=UserStatus.all_states)
        async def student_show_groups(message: types.Message):
            """
            Provide custom keyboard with student's groups
            :param message:
            :return:
            """

            self._cached_msgs.append(message.message_id)
            user_id = message.chat.id

            student_classrooms = []
            for group_id in self.db.find_one({"user_id": user_id})["classrooms"]:
                student_classrooms.append(self.class_db.get_info(group_id))

            keyboard = []
            for group in student_classrooms:
                keyboard.append([{group["name"]: f"{group['name']}:{group['classroom_id']}"}])

            self.last_msg_id = (await self.bot.send_message(user_id, "Here is a list of your classrooms. "
                                                                     "Select one to view available actions.",
                                                            reply_markup=await get_custom_keyboard(keyboard))
                                ).message_id
            await UserStatus.VIEW_GROUPS.set()

        @dispatcher.message_handler(lambda message: message.text in ["My marks"], state=UserStatus.all_states)
        async def student_show_marks(message: types.Message):
            """
            Get student's marks in every classroom
            :param message:
            :return:
            """

            self._cached_msgs.append(message.message_id)
            # TODO: fill

        @dispatcher.message_handler(lambda message: message.text in ["Deadlines"], state=UserStatus.all_states)
        async def student_show_deadlines(message: types.Message):
            """
            Get list of active deadlines
            :param message:
            :return:
            """

            self._cached_msgs.append(message.message_id)
            # TODO: fill

        @dispatcher.callback_query_handler(lambda callback: callback.data == CALLBACK_STUDENT_CLASSROOM_VIEW_TASKS,
                                           state=UserStatus.STUDENT_GROUPS_ACTIONS)
        async def student_submit_task(callback_query: types.CallbackQuery, state: FSMContext):
            """
            Submit a task
            Sends custom keyboard with a list of buttons (representing tasks)
            On click - switches to task and asks to send a text/image/file
            :param callback_query:
            :param state:
            :return:
            """

            user_id = callback_query.from_user.id

            await clean_chat(user_id)
            async with state.proxy() as data:
                classroom_id = data["classroom_id"]
                group_name = data["group_name"]
                await UserStatus.VIEW_TASKS.set()
                await state.update_data(data)

            student_tasks = self.class_db.get_info(classroom_id)["tasks"]

            keyboard = []
            msg_tasks_list = []
            for _id, task in enumerate(student_tasks):
                deadline = task["deadline"]
                msg_tasks_list.append(f"{_id + 1}) {task['description']}. Deadline {deadline.strftime('%d %B, %Y')}\n")
                keyboard.append([{f"Task {_id + 1} actions": f"{_id}:{classroom_id}"}])

            await self.bot.edit_message_text(f"{group_name} active tasks: \n{''.join(msg_tasks_list)}\n"
                                             f"Select task ID to view available actions.",
                                             callback_query.from_user.id,
                                             self.last_msg_id, reply_markup=await get_custom_keyboard(keyboard))

        @dispatcher.callback_query_handler(state=UserStatus.VIEW_TASKS)
        async def view_task_actions(callback_query: types.CallbackQuery, state: FSMContext):
            """
            Message with inline keyboard depicting available actions with the selected group
            (callback data stores group's ID)
            :param state:
            :param callback_query:
            :return:
            """

            array_task_id, group_id = callback_query.data.split(':')  # Store group ID and action performer's ID
            array_task_id = int(array_task_id)
            tasks = self.class_db.get_info(group_id)["tasks"]
            selected_task = tasks[array_task_id]

            if not self._user_type:
                self._user_type = self.db.get_type(callback_query.from_user.id)

            if self._user_type == "teacher":
                await UserStatus.TEACHER_TASK_ACTIONS.set()
                await state.update_data(classroom_id=group_id, task_id=selected_task["id"], array_task_id=array_task_id)
                reply_markup = await get_teacher_task_actions_keyboard(get_files=bool(selected_task["files"]),
                                                                       is_task_active=selected_task.get("active", True))
            else:
                await UserStatus.STUDENT_TASK_ACTIONS.set()
                await state.update_data(classroom_id=group_id, task_id=selected_task["id"], array_task_id=array_task_id)
                reply_markup = await get_student_task_actions_keyboard(get_files=bool(selected_task["files"]))
            await self.bot.edit_message_text(f"Task {array_task_id + 1} description: {selected_task['description']}\n"
                                             f"Available actions:",
                                             callback_query.from_user.id, self.last_msg_id, reply_markup=reply_markup)
            await self.bot.answer_callback_query(callback_query.id)

        @dispatcher.callback_query_handler(lambda callback: callback.data == CALLBACK_DOWNLOAD_TASK_ATTCHMENTS,
                                           state=UserStatus.all_states)
        async def download_attachments(callback_query: types.CallbackQuery, state: FSMContext):
            """
            Send selected task attachment to user
            Available states: UserState.STUDENT_TASK_ACTIONS, UserState.TEACHER_TASK_ACTIONS.
            :param callback_query:
            :param state:
            :return:
            """

            pass  # TODO: fill

        @dispatcher.callback_query_handler(lambda callback: callback.data == CALLBACK_SUBMIT_TASK,
                                           state=UserStatus.STUDENT_TASK_ACTIONS)
        async def student_submit_task(callback_query: types.CallbackQuery, state: FSMContext):
            """
            Ask student to send task answers (text and/or file) for further processing.
            :param callback_query:
            :param state:
            :return:
            """

            self._cached_msgs.append(self.last_msg_id)
            await clean_chat(callback_query.from_user.id)

            async with state.proxy() as data:
                await UserStatus.STUDENT_SUBMIT_TASK.set()
                await state.update_data(data)  # classroom_id, task_id, array_task_id
            self._cached_msgs.append((await self.bot.send_message(callback_query.from_user.id,
                                                                  "Please, send me your answer in the following form:\n"
                                                                  "1. Just text message with answer\n"
                                                                  "2. Text + file/image (any format - up to 15MB)\n"
                                                                  "3. Just file/image\n"
                                                                  "Use the attachment button to send me photos/files.")
                                      ).message_id)

        @dispatcher.message_handler(content_types=["text", "document", "photo"], state=UserStatus.STUDENT_SUBMIT_TASK)
        async def handle_student_task(message: types.Message, state: FSMContext):
            """
            Get student's answer on selected task
            :param message:
            :param state:
            :return:
            """
            user_id = message.chat.id
            await clean_chat(user_id)
            self._cached_msgs.append(message.message_id)

            text_answer = message.text

            if message.content_type == "photo":
                await message.photo[-1].download(destination_dir=get_temp_dir(user_id))
            elif message.content_type == "document":
                await message.document.download(destination_dir=get_temp_dir(user_id))
            # TODO: implement malware scanner

            async with state.proxy() as data:  # classroom_id, task_id, array_task_id
                task = Task(data["task_id"], data["classroom_id"], self.class_db, self.db, self.deadlines_db)
                task_files = [file for file in Path(get_temp_dir(user_id)).glob('**/*') if file.is_file()]
                for file in task_files:
                    task.add_file(file)
                    os.remove(str(file))
                if text_answer:
                    task.add_text_description(text_answer)
                # TODO: ASK IF READY TO SEND => YES=SEND, NO=INACTIVE(SEND LATER)

        @dispatcher.callback_query_handler(lambda callback: callback.data == CALLBACK_STUDENT_QUESTION,
                                           state=UserStatus.all_states)
        async def student_ask_question(callback_query: types.CallbackQuery, state: FSMContext):
            """
            Ask teacher a question.
            Available states: UserState.STUDENT_TASK_ACTIONS, UserState.STUDENT_GROUPS_ACTIONS
            :param callback_query:
            :param state:
            :return:
            """

            pass  # TODO: fill

        # endregion

        # region Teacher: main actions
        @dispatcher.message_handler(lambda message: message.text in ["Create group"], state=UserStatus.all_states)
        async def teacher_create_group(message: types.Message):
            self._cached_msgs.append(message.message_id)
            user_id = message.chat.id
            await clean_chat(user_id)
            await ask_classroom_name(chat_id=user_id)

        @dispatcher.message_handler(lambda message: message.text in ["Managed groups"], state=UserStatus.all_states)
        async def teacher_managed_groups(message: types.Message):
            """
            Provide custom keyboard with teacher's managed groups
            :param message:
            :return:
            """

            self._cached_msgs.append(message.message_id)
            user_id = message.chat.id
            await clean_chat(user_id)

            managed_classrooms = []
            for group_id in self.db.find_one({"user_id": user_id})["managed_classrooms"]:
                managed_classrooms.append(self.class_db.get_info(group_id))

            keyboard = []
            for group in managed_classrooms:
                keyboard.append([{group["name"]: f"{group['name']}:{group['classroom_id']}"}])

            self.last_msg_id = (await self.bot.send_message(user_id, "Here are your managed groups. "
                                                                     "Select one to view available actions.",
                                                            reply_markup=await get_custom_keyboard(keyboard))
                                ).message_id
            await UserStatus.VIEW_GROUPS.set()

        @dispatcher.callback_query_handler(state=UserStatus.VIEW_GROUPS)
        async def view_group_actions(callback_query: types.CallbackQuery, state: FSMContext):
            """
            Message with inline keyboard depicting available actions with the selected group
            (callback data stores group's ID)
            :param state:
            :param callback_query:
            :return:
            """

            group_name, group_id = callback_query.data.split(':')  # Store group ID and action performer's ID

            if not self._user_type:
                self._user_type = self.db.get_type(callback_query.from_user.id)

            if self._user_type == "teacher":
                await UserStatus.TEACHER_GROUPS_ACTIONS.set()
                await state.update_data(classroom_id=group_id, teacher_id=callback_query.from_user.id)
                reply_markup = await get_teacher_group_actions_keyboard()
            else:
                await UserStatus.STUDENT_GROUPS_ACTIONS.set()
                await state.update_data(classroom_id=group_id, group_name=group_name)
                reply_markup = await get_student_group_actions_keyboard()
            await self.bot.edit_message_text(f"Group {group_name} actions:", callback_query.from_user.id,
                                             self.last_msg_id, reply_markup=reply_markup)
            await self.bot.answer_callback_query(callback_query.id)

        @dispatcher.callback_query_handler(lambda callback: callback.data == CALLBACK_CREATE_TASK,
                                           state=UserStatus.TEACHER_GROUPS_ACTIONS)
        async def begin_create_task(callback_query: types.CallbackQuery, state: FSMContext):
            """
            Create task for students
            :param state:
            :param callback_query:
            :return:
            """

            await clean_chat(callback_query.from_user.id)
            async with state.proxy() as data:
                await UserStatus.TEACHER_CREATE_TASK.set()
                await state.update_data(data)
            self.last_msg_id = (await self.bot.send_message(callback_query.from_user.id,
                                                            "Please, send me the task in the following form:\n"
                                                            "1. Just text message with description\n"
                                                            "2. Text description + file (any format - up to 15MB)\n"
                                                            "3. Text description + image\n"
                                                            "Use the attachment button to send me photos/files.\n"
                                                            "Warning: don't send files "
                                                            "without text message description! Although it is possible,"
                                                            " description helps students to understand and estimate "
                                                            "the task quickly without opening full text.")
                                ).message_id

        @dispatcher.message_handler(content_types=["text", "document", "photo"], state=UserStatus.TEACHER_CREATE_TASK)
        async def handle_task_description(message: types.Message, state: FSMContext):
            """
            Get task information, store it in database and send to students
            :param state:
            :param message:
            :return:
            """

            user_id = message.chat.id
            await clean_chat(user_id)
            self._cached_msgs.append(message.message_id)

            description = message.text
            task_id = get_md5(f"{user_id}-{description}-{message.message_id}")

            if message.content_type == "photo":
                await message.photo[-1].download(destination_dir=get_temp_dir(user_id))
            elif message.content_type == "document":
                await message.document.download(destination_dir=get_temp_dir(user_id))
            # TODO: implement malware scanner
            async with state.proxy() as data:
                task = Task(task_id=task_id, classroom_id=data["classroom_id"],
                            classroom_db=self.class_db, user_db=self.db, deadlines_db=self.deadlines_db)
                if description:
                    task.add_text_description(description)
                task_files = [file for file in Path(get_temp_dir(user_id)).glob('**/*') if file.is_file()]
                for file in task_files:
                    task.add_file(file)
                    os.remove(str(file))
                task.prepare(user_id)

            await UserStatus.TEACHER_WAIT_TASK_DEADLINE.set()
            await state.update_data(task_id=task_id, creator_id=user_id, classroom_id=data["classroom_id"])
            self._cached_msgs.append((await self.bot.send_message(user_id,
                                                                  "Now send me the deadline for this task in any form, "
                                                                  "e.g. 26.04.2022 23:59 or 26 april 2022 23:59.")
                                      ).message_id)

        @dispatcher.message_handler(content_types=["text"], state=UserStatus.TEACHER_WAIT_TASK_DEADLINE)
        async def task_deadline_handler(message: types.Message, state: FSMContext):
            """
            Handle tasks's deadline date
            :param state:
            :param message:
            :return:
            """

            try:
                date = parse(message.text, dayfirst=True)
                async with state.proxy() as data:
                    task_id, classroom_id = data["task_id"], data["classroom_id"]
                    task = Task(task_id, classroom_id, self.class_db, self.db, self.deadlines_db)
                    task.set_deadline(date)
                    self.last_msg_id = (await self.bot.send_message(message.chat.id,
                                                                    "Your task is ready. Send it to students?",
                                                                    reply_markup=await get_yes_no_keyboard())
                                        ).message_id
                    await UserStatus.TEACHER_SEND_TASK.set()
                    await state.update_data(task_id=task_id, classroom_id=classroom_id)
            except ValueError:
                self._cached_msgs.append((await self.bot.send_message(message.chat.id,
                                                                      "Sorry, I couldn't recognize the date format. "
                                                                      "Try more clear format, e.g. 26.04.2022 23:59")
                                          ).message_id)

        @dispatcher.callback_query_handler(state=UserStatus.TEACHER_SEND_TASK)
        async def teacher_submit_task(callback_query: types.CallbackQuery, state: FSMContext):
            await clean_chat(callback_query.from_user.id)
            if callback_query.data == CALLBACK_YES:
                async with state.proxy() as data:
                    task = Task(data["task_id"], data["classroom_id"], self.class_db, self.db, self.deadlines_db)
                    await task.send_students(self.bot)
                self._cached_msgs.append((await self.bot.send_message(callback_query.from_user.id,
                                                                      "Task was successfully sent to students! "
                                                                      "You'll receive solutions after deadline comes.")
                                          ).message_id)
            else:
                async with state.proxy() as data:
                    task = Task(data["task_id"], data["classroom_id"], self.class_db, self.db, self.deadlines_db)
                    task.set_active(False)
                self._cached_msgs.append((await self.bot.send_message(callback_query.from_user.id,
                                                                      "Task was not sent to students. "
                                                                      "You will be able to send/modify it later "
                                                                      "in section 'classroom' - 'tasks'.")
                                          ).message_id)
        # endregion
