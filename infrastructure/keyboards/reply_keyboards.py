"""
ReplyMarkup keyboards (used as commands)
"""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


async def get_main_menu_markup(user_type: str = None) -> ReplyKeyboardMarkup:
    """
    Get main menu actions markup
    :returns: ReplyKeyboardMarkup
    """

    if user_type == "teacher":
        keyboard = [
            [
                KeyboardButton("Create group"),
                KeyboardButton("Managed groups"),
            ]
        ]
    elif user_type == "student":
        keyboard = [
            [
                KeyboardButton("Add group"),
                KeyboardButton("My groups"),
            ],
            [
                KeyboardButton("My marks"),
                KeyboardButton("Deadlines"),
            ]
        ]
    else:
        keyboard = [
            [
                KeyboardButton("Register")
            ]
        ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
