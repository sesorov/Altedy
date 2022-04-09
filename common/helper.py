"""
Useful classes, functions, etc.
"""

import re
from enum import Enum


class UserStatus(Enum):
    """
    Defines current user-bot interaction state
    """

    REGISTRATION = 0
    WAIT_EMAIL = 1
    WAIT_FULL_NAME = 2
    WAIT_CLASSROOM_ID = 3


class VerifyString(Enum):
    """
    A collection of regex validation strings
    """

    EMAIL = re.compile("([A-Za-z0-9]+[.-_])*[A-Za-z0-9]+@[A-Za-z0-9-]+(\.[A-Z|a-z]{2,})+")
    FULL_NAME = re.compile("[A-Za-z\-]{2,25}( [A-Za-z]{2,25})?( [A-Za-z]{2,25})?")
