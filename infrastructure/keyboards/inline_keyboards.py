"""
Inline keyboards (attached to messages)
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from infrastructure.keyboards.callbacks import *


async def get_help_keyboard() -> InlineKeyboardMarkup:
    """
    Chat help keyboard
    """
    keyboard = [
        [
            InlineKeyboardButton("Bot guide 1-1", callback_data=''),
            InlineKeyboardButton("Bot guide 1-2", callback_data='')
        ],
        [
            InlineKeyboardButton("Bot guide 2-1", callback_data=''),
            InlineKeyboardButton("Bot guide 2-2", callback_data='')
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


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
