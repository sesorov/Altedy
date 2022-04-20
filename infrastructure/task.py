"""
General class for task actions
"""

import os
import datetime

from pathlib import Path

from aiogram import Bot
from bson.binary import Binary

from common.helper import get_temp_dir
from configs.logger_conf import configure_logger
from database.database import UserDatabase, ClassroomDatabase

LOGGER = configure_logger(__name__)


# pylint: disable = logging-fstring-interpolation, unnecessary-pass


class Task:
    """
    Task actions & some database interactions wrappers
    """

    def __init__(self, task_id, classroom_id, classroom_db, user_db):
        self._task_id = task_id
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

    def set_deadline(self, date: datetime.datetime):
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

    def prepare(self, creator_id):
        """
        Initial task actions after submitting all the files/descriptions
        :param creator_id:
        :return:
        """

        LOGGER.info("Uploading task info to MongoDB")
        task_info = {
            "files": self._files,
            "description": self._description
        }
        self._classroom_db.add_task(task_id=self._task_id, creator_id=creator_id,
                                    classroom_id=self._classroom_id, info=task_info)

    async def send_students(self, bot: Bot):
        """
        Send task to students

        This function gets task info (files and/or description),
        decodes files binary strings and sends them to students from
        classroom list.
        :return:
        """

        classroom_info = self._classroom_db.get_info(self._classroom_id)

        # task-related variables
        files = {}
        creator_id = None
        description = None
        deadline = None

        for task in classroom_info["tasks"]:
            if task["id"] == self._task_id:
                files = {file["filename"]: file["file"] for file in task["files"]}
                creator_id, description, deadline = task["creator_id"], task["description"], task["deadline"]
                break

        for student in classroom_info["students"]:
            await bot.send_message(student["id"], f"Greetings! You've received a new task:\n{description}\n"
                                                  f"Deadline: {deadline}\n"
                                                  f"Good luck!")
            if files:
                for filename, file_bin in files.items():
                    file_path = Path(get_temp_dir(creator_id) / filename)
                    with open(file_path, "wb+") as handler:
                        handler.write(Binary(file_bin))
                    with open(file_path, "rb") as handler:
                        await bot.send_document(student["id"], (filename, handler))
                    os.remove(file_path)
