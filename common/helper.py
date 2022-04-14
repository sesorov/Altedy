"""
Useful classes, functions, etc.
"""

import re
import hashlib
from enum import Enum

from aiogram.dispatcher.filters.state import State, StatesGroup


class UserStatus(StatesGroup):
    """
    Defines current user-bot interaction state
    """

    REGISTRATION = State()
    WAIT_EMAIL = State()
    WAIT_FULL_NAME = State()
    WAIT_CLASSROOM_NAME = State()

    MAIN_MENU = State()

    STUDENT_ADD_GROUP = State()

    TEACHER_VIEW_GROUPS = State()
    TEACHER_CREATE_TASK = State()


class VerifyString(Enum):
    """
    A collection of regex validation strings
    """

    EMAIL = re.compile("([A-Za-z0-9]+[.-_])*[A-Za-z0-9]+@[A-Za-z0-9-]+(\.[A-Z|a-z]{2,})+")
    FULL_NAME = re.compile("[A-Za-z\-]{2,25}( [A-Za-z]{2,25})?( [A-Za-z]{2,25})?")


def get_md5(value):
    """
    Get MD5 of the value
    :param value:
    :return:
    """

    return hashlib.md5(str(value).encode()).hexdigest()
