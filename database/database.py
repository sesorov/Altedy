import sys
import time
import json
import pymongo

from pathlib import Path

from configs.logger_conf import configure_logger
from common.helper import UserStatus
from configs.bot_conf import ConfigException

LOGGER = configure_logger(__name__)


class Database:
    """
    General wrapper class for MongoDB default methods
    """

    def __init__(self, url, db_name, default_collection=None):
        self.client = pymongo.MongoClient(url)
        self.db_name = db_name
        self.default_collection = default_collection

    def upload(self, primary_key, data, collection_name=None):
        """
        Upload/update data in MongoDB
        :param collection_name: Name of db collection to upload info in
        :param primary_key: For updating data
        :param data: Data to be uploaded
        :return: None
        """

        if not collection_name:
            collection_name = self.default_collection

        collection = self.client[self.db_name][collection_name]
        collection.replace_one(primary_key, data, upsert=True)
        LOGGER.info(f"Uploaded data to MongoDB: {primary_key}")

    def aggregate(self, aggregation: list, collection_name=None):
        """
        Aggregate info from MongoDB
        :param collection_name:
        :param aggregation:
        :return: list
        """

        if not collection_name:
            collection_name = self.default_collection

        collection = self.client[self.db_name][collection_name]
        return list(collection.aggregate(aggregation))

    def find(self, collection_name=None, query=None):
        """
        Find info by query. Leave query empty if need to extract all data
        :param collection_name:
        :param query:
        :return: list
        """

        if query is None:
            query = {}

        if not collection_name:
            collection_name = self.default_collection

        collection = self.client[self.db_name][collection_name]
        return list(collection.find(query))

    def find_one(self, collection_name=None, query=None):
        """
        Find only one exact record by query. Leave query empty if need to extract all data
        :param collection_name:
        :param query:
        :return: dict
        """

        if query is None:
            query = {}

        if not collection_name:
            collection_name = self.default_collection

        collection = self.client[self.db_name][collection_name]
        return collection.find_one(query)

    def update(self, user_id, info: dict, collection_name=None):
        """
        Update user information on MongoDB
        :param user_id: users's telegram id
        :param info: dict containing info for update
        :return: None
        """

        if not collection_name:
            collection_name = self.default_collection

        collection = self.client[self.db_name][collection_name]
        collection.update_one({"user_id": user_id}, {"$set": info}, upsert=True)


class UserDatabase(Database):
    """
    Handler class for users actions in DB
    """

    _default_file_path = Path(__file__).resolve().parent / "database_config.json"

    def __init__(self):
        self._data = self._load_from_json()["users"]
        super().__init__(url=self._data["url"], db_name=self._data["db_name"], default_collection=self._data["collection"])

    def _load_from_json(self) -> dict:
        try:
            with open(self._default_file_path, encoding="utf-8") as cfg_file:
                return json.load(cfg_file)
        except IOError as err:
            raise ConfigException(f"Cannot open file '{self._default_file_path}'") from err

    def get_users(self, user_type=None):
        """
        Get list of all users from DB by type (none=all, students, teachers)
        :param user_type: str students/teachers/None=all
        :return: list
        """

        if user_type == "students":
            students = self.aggregate([
                {
                    "$match": {'type': 'student'}
                }
            ])
            if students:
                LOGGER.info(f"Successfully got {len(students)} students info.")
            else:
                LOGGER.warning(f"No students found in {self.db_name}.{self.default_collection}")
            return students
        elif user_type == "teachers":
            teachers = self.aggregate([
                {
                    "$match": {'type': 'teacher'}
                }
            ])
            if teachers:
                LOGGER.info(f"Successfully got {len(teachers)} teachers info.")
            else:
                LOGGER.warning(f"No teachers found in {self.db_name}.{self.default_collection}")
            return teachers
        else:
            users = list(self.find({}))
            if users:
                LOGGER.info(f"Successfully got {len(users)} users info.")
            else:
                LOGGER.warning(f"No users found in {self.db_name}.{self.default_collection}")
            return users

    def get_type(self, user_id):
        """
        Get user type: student or teacher
        :param user_id:
        :return:
        """

        return self.find_one({"user_id": user_id})["type"]

    def get_status(self, user_id) -> UserStatus:
        """
        Get user status in chat (from common.helper.UserStatus)

        :return: UserStatus
        """

        return UserStatus(self.find_one({"user_id": user_id})["status"])

    def set_status(self, user_id, status: UserStatus):
        """
        Set user status in chat (from common.helper.UserStatus)
        :param user_id:
        :param status:
        :return:
        """

        self.update(user_id, {"status": status.value})

    def add_raw(self, user_id, additional: dict = None):
        """
        Add record for not yet registered user

        :param user_id: int
        :param additional: any other parameters
        :return: None
        """

        if additional is None:
            additional = {}

        if additional.get("status", None) is None:
            additional["status"] = UserStatus.REGISTRATION.value

        info = {**{"user_id": user_id}, **additional}

        self.upload({"user_id": user_id}, info)


class User:
    def __init__(self, user_id, first_name, surname, username):
        self.user_id = user_id
        self.first_name = first_name
        self.surname = surname,
        self.username = username
        self.db: UserDatabase = UserDatabase()

    def __str__(self):
        """
        Get user's name if possible (ID otherwise)
        :returns: str
        """
        if self.username:
            return f"@{self.username}"
        elif self.first_name or self.surname:
            return f"{self.first_name} {self.surname}"
        else:
            return str(self.user_id)

    def upload_info(self, additional: dict = None):
        """
        Upload user info to MongoDB
        :additional dict: Dict of any additional information
        :return: None
        """
        if additional is None:
            additional = {}
        personal_data = {
            "user_id": self.user_id,
            "username": self.username,
            "first_name": self.first_name,
            "surname": self.surname,
        }
        self.db.upload({"user_id": self.user_id}, {**personal_data, **additional})


class Student(User):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def upload_info(self, additional: dict = None):
        if additional is None:
            additional = {}
        additional.update({"type": "student"})
        super().upload_info(additional=additional)


class Teacher(User):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def upload_info(self, additional: dict = None):
        if additional is None:
            additional = {}
        additional.update({"type": "teacher"})
        super().upload_info(additional=additional)
