"""
General class for task actions
"""

import datetime
from bson.binary import Binary
from pathlib import Path

from configs.logger_conf import configure_logger
from database.database import UserDatabase, ClassroomDatabase

LOGGER = configure_logger(__name__)


class Task:
    def __init__(self, task_id, creator_id, classroom_id, classroom_db, user_db):
        self._task_id = task_id
        self._creator_id = creator_id
        self._classroom_id = classroom_id

        self._classroom_db: ClassroomDatabase = classroom_db
        self._user_db: UserDatabase = user_db

        self._files = []
        self._description = "See attachments"

    def add_file(self, file_path):
        """
        Add file to task

        :param file_path:
        :return:
        """
        with open(file_path, "rb") as file:
            encoded = Binary(file.read())
        filename = Path(file_path).name

        self._files.append({
            "filename": filename,
            "file": encoded
        })
        LOGGER.info(f"[Task] Added file for uploading to DB: {filename}")

    def add_text_description(self, description):
        """
        Add text task description
        :param description:
        :return:
        """

        self._description = description
        LOGGER.info("[Task] Updated description")

    def set_deadline(self, date: datetime):
        """
        Add/update task deadline

        :param date:
        :return:
        """

        LOGGER.info("[Task] Trying to update deadline")
        tasks = self._classroom_db.find_one({"classroom_id": self._classroom_id})["tasks"]
        element_id = None
        for index, element in enumerate(tasks):
            if element["id"] == self._task_id:
                element_id = index
                break
        self._classroom_db.update({"classroom_id": self._classroom_id}, {f"tasks.{element_id}.deadline": date})

    def prepare(self):
        """
        Initial task actions after submitting all the files/descriptions
        :return:
        """

        LOGGER.info("Uploading task info to MongoDB")
        task_info = {
            "files": self._files,
            "description": self._description
        }
        self._classroom_db.add_task(task_id=self._task_id, creator_id=self._creator_id,
                                    classroom_id=self._classroom_id, info=task_info)
