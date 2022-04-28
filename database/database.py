"""
Database general operations and handlers
Designed for MongoDB
Edit database_config.json for custom settings
"""

import json

from pathlib import Path
from datetime import datetime

import pymongo

from configs.logger_conf import configure_logger
from configs.bot_conf import ConfigException

LOGGER = configure_logger(__name__)


# pylint: disable = too-many-lines, no-name-in-module, import-error, multiple-imports, logging-fstring-interpolation


def _load_from_json(_path) -> dict:
    try:
        with open(_path, encoding="utf-8") as cfg_file:
            return json.load(cfg_file)
    except IOError as err:
        raise ConfigException(f"Cannot open file '{_path}'") from err


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
        res = list(collection.aggregate(aggregation))
        LOGGER.info(f"Found {len(res)} items by aggregation: {aggregation}")
        return res

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
        res = list(collection.find(query))
        LOGGER.info(f"Found {len(res)} items by query: {query}")
        return res

    def find_one(self, query=None, collection_name: str = None):
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
        res = collection.find_one(query)
        if res:
            LOGGER.info(f"Found record: {res} by query: {query}")
        else:
            LOGGER.warning(f"Nothing found by query: {query}")
        return res

    def update(self, primary_key: dict, info: dict, collection_name=None) -> bool:
        """
        Update information on MongoDB
        :param collection_name:
        :param primary_key: key to find data to update (e.g. {"user_id": user_id}
        :param info: dict containing info for update
        :return: bool
        """

        if not collection_name:
            collection_name = self.default_collection

        collection = self.client[self.db_name][collection_name]
        response = collection.update_one(primary_key, {"$set": info}, upsert=True).raw_result
        if response['n']:
            LOGGER.info(f"Successfully updated {response['n']} record. Response from mongoDB: {response}")
            return True
        LOGGER.warning(f"Could not find anything to update. Check key: {primary_key}, response: {response}")
        return False

    def array_remove(self, primary_key: dict, array_name: str, array_key: dict, collection_name=None) -> bool:
        """
        Remove element from array in MongoDB

        :param primary_key: To find record in MongoDB
        :param array_name: Array to remove element from
        :param array_key: Key to find the element to remove
        :param collection_name:
        :return:
        """

        if not collection_name:
            collection_name = self.default_collection

        collection = self.client[self.db_name][collection_name]
        response = collection.update_one(primary_key, {'$pull': {array_name: array_key}}).raw_result
        if response['n']:
            LOGGER.info(f"Successfully updated {response['n']} record. Response from mongoDB: {response}")
            return True
        LOGGER.warning(f"Could not find anything to remove. "
                       f"Check key: {primary_key}, array_name: {array_name}, response: {response}")
        return False

    def array_append(self, primary_key, array_name, *elements, collection_name=None) -> bool:
        """
        Add element to array in MongoDB record

        :param array_name: Array to append elements to
        :param primary_key: key to find data to update (e.g. {"user_id": user_id}
        :param collection_name:
        :param elements: Elements to append to array
        :return:
        """

        if not collection_name:
            collection_name = self.default_collection

        collection = self.client[self.db_name][collection_name]
        response = collection.update_one(primary_key, {'$push': {array_name: {'$each': elements}}}).raw_result
        if response['n']:
            LOGGER.info(f"Successfully updated {response['n']} record. Response from mongoDB: {response}")
            return True
        LOGGER.warning(f"Could not find anything to update. "
                       f"Check key: {primary_key}, array_name: {array_name}, response: {response}")
        return False

    def move_element(self, primary_key, array_from, element_id, array_to, collection_name=None) -> bool:
        """
        Move element from one array to another.
        Example use case: archive tasks

        :param primary_key: key to find a MongoDB record with array_from
        :param array_from: name of array from element will be moved
        :param element_id: id array element to move
        :param array_to: name of array to which an element will be moved
        :param collection_name: leave empty to use the default one
        :return: bool response (success/fail)
        """

        if not collection_name:
            collection_name = self.default_collection
        collection = self.client[self.db_name][collection_name]

        record = collection.find_one(primary_key)
        element = record[array_from][element_id]

        response = collection.update(primary_key, {
            "$pull": {array_from: element},
            "$addToSet": {array_to: element}
        })
        if response['n']:
            LOGGER.info(f"Successfully updated {response['n']} record. Response from mongoDB: {response}")
            return True
        LOGGER.warning(f"Could not find anything to move. "
                       f"Check key: {primary_key}, array_from: {array_from}, array_to: {array_to}, el_id: {element_id}")
        return False


class UserDatabase(Database):
    """
    Handler class for users actions in DB
    """

    _default_file_path = Path(__file__).resolve().parent.parent / "configs" / "database_config.json"

    def __init__(self):
        self._data = _load_from_json(self._default_file_path)["users"]
        super().__init__(url=self._data["url"], db_name=self._data["db_name"],
                         default_collection=self._data["collection"])

    def update(self, user_id, info: dict, collection_name=None):  # pylint: disable=arguments-renamed
        """
        Update information on MongoDB
        :param user_id:
        :param info:
        :param collection_name:
        :return:
        """
        super().update({"user_id": user_id}, info, collection_name)

    def exists(self, user_id) -> bool:
        """
        Check if user with this ID exists
        :param user_id:
        :return:
        """

        return bool(self.find_one({"user_id": user_id}))

    def get_type(self, user_id):
        """
        Get user type: student or teacher
        :param user_id:
        :return:
        """

        return self.find_one({"user_id": user_id})["type"]

    def add_raw(self, user_id, additional: dict = None):
        """
        Add record for not yet registered user

        :param user_id: int
        :param additional: any other parameters
        :return: None
        """

        if additional is None:
            additional = {}

        info = {**{"user_id": user_id}, **additional}

        self.upload({"user_id": user_id}, info)


class ClassroomDatabase(Database):
    """
    Handler class for users actions in DB
    """

    _default_file_path = Path(__file__).resolve().parent.parent / "configs" / "database_config.json"

    def __init__(self):
        self._data = _load_from_json(self._default_file_path)["classrooms"]
        super().__init__(url=self._data["url"], db_name=self._data["db_name"],
                         default_collection=self._data["collection"])

    def get_info(self, classroom_id) -> dict:
        """
        Get group info

        :param classroom_id:
        :return: {'_id': ObjectID, 'name': ..., 'classroom_id': ..., 'teachers': [...], 'students': [...]}
        """

        return self.find_one({"classroom_id": classroom_id})

    def add_raw(self, classroom_id, teacher_id, additional: dict = None):
        """
        Add record for a new classroom

        :param classroom_id:
        :param teacher_id:
        :param additional: any other parameters
        :return: None
        """

        if additional is None:
            additional = {}

        info = {**{"classroom_id": classroom_id, "teachers": [teacher_id]}, **additional}

        self.upload({"classroom_id": classroom_id}, info)

    def add_student(self, student_id, classroom_id):
        """
        Add student to group

        :param student_id:
        :param classroom_id:
        :return:
        """

        return self.array_append({"classroom_id": classroom_id}, "students", {"id": student_id}, collection_name=None)

    def add_teacher(self, teacher_id, classroom_id):
        """
        Add teacher to group (has manager access)

        :param teacher_id:
        :param classroom_id:
        :return:
        """

        return self.array_append({"classroom_id": classroom_id}, "teachers", {"id": teacher_id}, collection_name=None)

    def add_task(self, task_id, creator_id, classroom_id, info: dict):
        """
        Add task for group

        :param info:
        :param classroom_id:
        :param task_id:
        :param creator_id:
        :return:
        """

        return self.array_append({"classroom_id": classroom_id}, "tasks",
                                 {"id": task_id, "creator_id": creator_id, **info}, collection_name=None)

    def submit_task(self, student_id, classroom_id, info: dict):
        """
        Send student's answer to database

        :param student_id:
        :param classroom_id:
        :param info:
        :return:
        """

        students_list = self.find_one({"classroom_id": classroom_id})["students"]
        student_array_id = None
        for index, student in enumerate(students_list):
            if student["id"] == student_id:
                student_array_id = index
                break

        self.array_remove({"classroom_id": classroom_id}, f"students.{student_array_id}.tasks",
                          {"task_id": info["task_id"]})
        self.array_append({"classroom_id": classroom_id}, f"students.{student_array_id}.tasks", info)


class DeadlineDatabase(Database):
    """
    Handler class for users actions in DB
    """

    _default_file_path = Path(__file__).resolve().parent.parent / "configs" / "database_config.json"

    def __init__(self):
        self._data = _load_from_json(self._default_file_path)["deadlines"]
        super().__init__(url=self._data["url"], db_name=self._data["db_name"],
                         default_collection=self._data["collection"])

    def add_deadline(self, classroom_id, task_id, date, additional: dict = None):
        """
        Add deadline to database for further notice
        :param additional:
        :param classroom_id:
        :param task_id:
        :param date:
        :return:
        """

        if additional is None:
            additional = {}

        info = {**{"task_id": task_id, "classroom_id": classroom_id, "date": date}, **additional}

        self.upload({"task_id": task_id}, info)

    def get_deadlines_between(self, date_from, date_to):
        """
        Get list of deadlines between two dates
        (one day and different hours/minutes/seconds is a possible case)
        :param date_from:
        :param date_to:
        :return:
        """

        return self.find(query={"date": {"$gte": date_from, "$lt": date_to}})

    def get_today_deadlines(self):
        """
        Get list of current day deadlines
        (from 00:00 to 23:59 of todays's date)
        :return:
        """

        today = datetime.today()
        today_begin = today.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today.replace(hour=23, minute=59, second=59, microsecond=999)
        return self.get_deadlines_between(today_begin, today_end)
