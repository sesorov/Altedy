"""
Useful classes, functions, etc.
"""

import re
import hashlib
from enum import Enum


class UserStatus(Enum):
    """
    Defines current user-bot interaction state
    """

    REGISTRATION = 0
    WAIT_EMAIL = 1
    WAIT_FULL_NAME = 2
    WAIT_CLASSROOM_NAME = 3

    MAIN_MENU = 4

    STUDENT_ADD_GROUP = 5


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
