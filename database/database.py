import sys
import time
import pymongo

from configs.logger_conf import configure_logger

LOGGER = configure_logger(__name__)


class Database:
    """
    Handler class for MongoDB
    """

    DATABASE_URL = "localhost:27017"
    DATABASE = "altedy"
    DB_COLLECTION = "users"

    def __init__(self):
        self.client = pymongo.MongoClient(self.DATABASE_URL)
        self.collection = self.client[self.DATABASE][self.DB_COLLECTION]

    def get_users(self, user_type=None):
        """
        Get list of all users from DB by type (none=all, students, teachers)
        :param user_type: str students/teachers/None=all
        :return: list
        """
        if user_type == "students":
            students = list(self.collection.aggregate([
                {
                    "$match": {'type': 'student'}
                }
            ]))
            if students:
                LOGGER.info(f"Successfully got {len(students)} students info.")
            else:
                LOGGER.warning(f"No students found in {self.DATABASE}.{self.DB_COLLECTION}")
            return students
        elif user_type == "teachers":
            teachers = list(self.collection.aggregate([
                {
                    "$match": {'type': 'teacher'}
                }
            ]))
            if teachers:
                LOGGER.info(f"Successfully got {len(teachers)} teachers info.")
            else:
                LOGGER.warning(f"No teachers found in {self.DATABASE}.{self.DB_COLLECTION}")
            return teachers
        else:
            users = list(self.collection.find({}))
            if users:
                LOGGER.info(f"Successfully got {len(users)} users info.")
            else:
                LOGGER.warning(f"No users found in {self.DATABASE}.{self.DB_COLLECTION}")
            return users

    def upload(self, primary_key, data):
        """
        Upload/update data in MongoDB
        :param primary_key: For updating data
        :param data: Data to be uploaded
        :return: None
        """
        self.collection.replace_one(primary_key, data, upsert=True)
        LOGGER.info(f"Uploaded data to MongoDB: {primary_key}")


class User:
    def __init__(self, user_id, first_name, surname, username):
        self.user_id = user_id
        self.first_name = first_name
        self.surname = surname,
        self.username = username
        self.db: Database = Database()

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
