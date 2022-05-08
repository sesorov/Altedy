"""
Inline keyboards (attached to messages)
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from infrastructure.keyboards.callbacks import *


async def get_custom_keyboard(buttons: list) -> InlineKeyboardMarkup:
    """
    Create custom keyboard with dynamic buttons
    Receives list of lists of dicts, where each list represents a row of buttons (dicts - name and callback)

    :param buttons: List of lists of dicts, e.g.: [[{'row_1_1': 11}, {...}], [{'row_2_1': 21}, {...}]]
    :return:
    """

    keyboard = InlineKeyboardMarkup()
    for row in buttons:
        keyboard.add(*[InlineKeyboardButton(list(button.items())[0][0], callback_data=list(button.items())[0][1])
                       for button in row])
    return keyboard


async def get_register_keyboard() -> InlineKeyboardMarkup:
    """
    First time registration / signing in
    """

    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("Register", callback_data=CALLBACK_REGISTER_1),
        InlineKeyboardButton("Sign in", callback_data=CALLBACK_SIGNIN),
    )
    return keyboard


async def get_student_teacher_keyboard() -> InlineKeyboardMarkup:
    """
    Select mode
    """

    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("Student", callback_data=CALLBACK_IS_STUDENT),
        InlineKeyboardButton("Teacher", callback_data=CALLBACK_IS_TEACHER),
    )
    return keyboard


async def get_ask_email_keyboard() -> InlineKeyboardMarkup:
    """
    Whether to share email with bot to receive notifications or not
    """

    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("Yes", callback_data=CALLBACK_EMAIL_TRUE),
        InlineKeyboardButton("No", callback_data=CALLBACK_EMAIL_FALSE),
    )
    return keyboard


async def get_teacher_group_actions_keyboard() -> InlineKeyboardMarkup:
    """
    View available TEACHER's actions in selected group
    """

    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("Create task", callback_data=CALLBACK_CREATE_TASK),
        InlineKeyboardButton("Active tasks", callback_data=CALLBACK_TEACHER_CLASSROOM_VIEW_TASKS),
        InlineKeyboardButton("Plugins", callback_data=CALLBACK_SETUP_PLUGINS),
    )
    return keyboard


async def get_student_group_actions_keyboard() -> InlineKeyboardMarkup:
    """
    View available TEACHER's actions in selected group
    """

    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("My tasks", callback_data=CALLBACK_STUDENT_CLASSROOM_VIEW_TASKS),
        InlineKeyboardButton("My marks", callback_data=CALLBACK_STUDENT_CLASSROOM_VIEW_MARKS),
        InlineKeyboardButton("Group materials", callback_data=CALLBACK_STUDENT_CLASSROOM_MATERIALS),
        InlineKeyboardButton("Ask a question", callback_data=CALLBACK_STUDENT_QUESTION),
    )
    return keyboard


async def get_teacher_task_actions_keyboard(get_files: bool = False,
                                            is_task_active: bool = True) -> InlineKeyboardMarkup:
    """
    View available TEACHER's actions in selected task
    :param is_task_active: Whether to display Activate button or not
    :param get_files: Whether to display Download Files button or not
    :return:
    """

    keyboard = InlineKeyboardMarkup()
    if get_files:
        keyboard.add(
            InlineKeyboardButton("Download attachments", callback_data=CALLBACK_DOWNLOAD_TASK_ATTCHMENTS),
        )
    if not is_task_active:
        keyboard.add(
            InlineKeyboardButton("Activate and send", callback_data=CALLBACK_SEND_TASK),
        )
    keyboard.add(
        InlineKeyboardButton("Get answers", callback_data=CALLBACK_GET_TASK_ANSWERS),
        InlineKeyboardButton("Delete task", callback_data=CALLBACK_DELETE_TASK),
    )
    return keyboard


async def get_student_task_actions_keyboard(get_files: bool = False) -> InlineKeyboardMarkup:
    """
    View available STUDENT's actions in selected task
    :param get_files: Whether to display Download Files button or not
    :return:
    """

    keyboard = InlineKeyboardMarkup()
    if get_files:
        keyboard.add(
            InlineKeyboardButton("Download attachments", callback_data=CALLBACK_DOWNLOAD_TASK_ATTCHMENTS),
        )
    keyboard.add(
        InlineKeyboardButton("Submit answer", callback_data=CALLBACK_SUBMIT_TASK),
        InlineKeyboardButton("Ask a question", callback_data=CALLBACK_STUDENT_QUESTION),
    )
    return keyboard


async def get_yes_no_keyboard() -> InlineKeyboardMarkup:
    """
    Simple yes/no inline keyboard. Use with states machine for correct work
    :return:
    """
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("Yes", callback_data=CALLBACK_YES),
        InlineKeyboardButton("No", callback_data=CALLBACK_NO)
    )
    return keyboard
