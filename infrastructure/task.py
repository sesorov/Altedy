"""
General class for task actions
"""

import os

from datetime import datetime, timedelta
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from aiogram import Bot
from bson.binary import Binary

from common.helper import get_temp_dir
from configs.logger_conf import configure_logger
from database.database import UserDatabase, ClassroomDatabase, DeadlineDatabase

LOGGER = configure_logger(__name__)
SCHEDULER = BackgroundScheduler()


# pylint: disable = logging-fstring-interpolation, unnecessary-pass


def check_deadlines(bot: Bot):
    """
    Auto-checker for upcoming deadlines.
    Checks if today is deadline for any task.
    If so, checks every hour if it has deadlines, then every minute (only if deadlines found)
    :param bot: Bot instance for notification sending
    :return:
    """

    LOGGER.info("Starting deadlines check job.")
    SCHEDULER.add_job(lambda: job_daily_deadlines(bot), "interval", hours=24, id='daily_deadlines_check')
    SCHEDULER.start()


def job_daily_deadlines(bot: Bot):
    """
    Daily running job that checks today's deadlines
    :return:
    """

    deadlines_db = DeadlineDatabase()   # probably should optimize databases instances
    if deadlines_db.get_today_deadlines():
        LOGGER.info("Found deadlines for today. Starting hourly check...")
        SCHEDULER.add_job(lambda: job_hourly_deadlines(bot), "interval", hours=1, id='hourly_deadlines_check')
    LOGGER.info("Daily deadlines check started.")


def job_hourly_deadlines(bot: Bot):
    """
    Hourly running job that checks current hour's deadlines
    Executes only when current DAY has deadlines
    :return:
    """

    deadlines_db = DeadlineDatabase()

    current_time = datetime.today()
    begin_time = current_time.replace(hour=current_time.hour, minute=0, second=0, microsecond=0)
    end_time = begin_time + timedelta(hours=1)
    if deadlines_db.get_deadlines_between(begin_time, end_time):
        LOGGER.info("Found deadlines for current hour. Starting minutely check...")
        SCHEDULER.remove_job('hourly_deadlines_check')
        SCHEDULER.add_job(lambda: job_minutely_deadlines(bot), "interval", minutes=1, id='minutely_deadlines_check')


def job_minutely_deadlines(bot: Bot):
    """
    Minutely running job that checks current minute's deadlines
    Executes only when current HOUR has deadlines
    :return:
    """

    deadlines_db = DeadlineDatabase()

    current_time = datetime.today()
    begin_time = current_time.replace(second=0, microsecond=0)
    end_time = begin_time + timedelta(minutes=1)
    current_deadlines = deadlines_db.get_deadlines_between(begin_time, end_time)
    if current_deadlines:
        LOGGER.info("Found deadlines for current minute.")
        SCHEDULER.remove_job('minutely_deadlines_check')  # Add actions for deadline
        print(bot.id)  # debug


class Task:
    """
    Task actions & some database interactions wrappers
    """

    def __init__(self, task_id, classroom_id,   # pylint: disable=too-many-arguments
                 classroom_db=None, user_db=None, deadlines_db=None):
        self._task_id = task_id
        self._classroom_id = classroom_id

        self._classroom_db: ClassroomDatabase = classroom_db or ClassroomDatabase()
        self._user_db: UserDatabase = user_db or UserDatabase()
        self._deadlines_db: DeadlineDatabase = deadlines_db or DeadlineDatabase()

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

    def set_active(self, active: bool = True):
        """
        Activate/deactivate (old) tasks
        :param active:
        :return:
        """

        LOGGER.info(f"[Task] Trying to set activeness status: {active}")
        tasks = self._classroom_db.find_one({"classroom_id": self._classroom_id})["tasks"]
        element_id = None
        for index, element in enumerate(tasks):
            if element["id"] == self._task_id:
                element_id = index
                break
        self._classroom_db.update({"classroom_id": self._classroom_id}, {f"tasks.{element_id}.active": active})

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
                self._deadlines_db.add_deadline(self._classroom_id, self._task_id, deadline)
                self.set_active()
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
