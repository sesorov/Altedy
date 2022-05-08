"""
Useful classes, functions, etc.
"""

import os
import re
import hashlib
from enum import Enum
from pathlib import Path

from aiogram.dispatcher.filters.state import State, StatesGroup


def get_temp_dir(subdir_name=None):
    """
    Get temp dir
    :param subdir_name:
    :return:
    """

    tempdir_path = Path(__file__).resolve().parent.parent / "temp" / f"{subdir_name}"
    tempdir_path.mkdir(parents=True, exist_ok=True)
    return tempdir_path


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
    STUDENT_GROUPS_ACTIONS = State()
    STUDENT_TASK_ACTIONS = State()
    STUDENT_SUBMIT_TASK = State()

    VIEW_GROUPS = State()
    VIEW_TASKS = State()

    TEACHER_GROUPS_ACTIONS = State()
    TEACHER_TASK_ACTIONS = State()
    TEACHER_CREATE_TASK = State()
    TEACHER_WAIT_TASK_DEADLINE = State()
    TEACHER_SEND_TASK = State()
    TEACHER_SETUP_PLUGINS = State()


class VerifyString(Enum):
    """
    A collection of regex validation strings
    """

    EMAIL = re.compile(r"([A-Za-z0-9]+[.-_])*[A-Za-z0-9]+@[A-Za-z0-9-]+(\.[A-Z|a-z]{2,})+")
    FULL_NAME = re.compile(r"[A-Za-z\-]{2,25}( [A-Za-z]{2,25})?( [A-Za-z]{2,25})?")


def get_md5(value):
    """
    Get MD5 of the value
    :param value:
    :return:
    """

    return hashlib.md5(str(value).encode()).hexdigest()  # nosec


def get_plugins() -> list:
    """
    Get list of plugins presented in nn_modules
    :return:
    """

    return next(os.walk(Path(__file__).resolve().parent.parent / "nn_modules"))[1]
