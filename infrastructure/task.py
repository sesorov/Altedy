"""
General class for task actions
"""

import os

from datetime import datetime, timedelta
from pathlib import Path
from shutil import make_archive, rmtree

import xlsxwriter

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from bson.binary import Binary

from common.helper import get_temp_dir
from configs.logger_conf import configure_logger
from database.database import UserDatabase, ClassroomDatabase, DeadlineDatabase
from infrastructure.keyboards.reply_keyboards import get_main_menu_markup

LOGGER = configure_logger(__name__)
SCHEDULER = AsyncIOScheduler()


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


async def job_daily_deadlines(bot: Bot):
    """
    Daily running job that checks today's deadlines
    :return:
    """

    deadlines_db = DeadlineDatabase()  # probably should optimize databases instances
    if deadlines_db.get_today_deadlines():
        LOGGER.info("Found deadlines for today. Starting hourly check...")
        SCHEDULER.add_job(lambda: job_hourly_deadlines(bot), "interval", hours=1, id='hourly_deadlines_check')
    LOGGER.info("Daily deadlines check started.")


async def job_hourly_deadlines(bot: Bot):
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


async def job_minutely_deadlines(bot: Bot):
    """
    Minutely running job that checks current minute's deadlines
    Executes only when current HOUR has deadlines
    :return:
    """

    deadlines_db = DeadlineDatabase()
    classroom_db = ClassroomDatabase()

    current_time = datetime.today()
    begin_time = current_time.replace(second=0, microsecond=0)
    end_time = begin_time + timedelta(minutes=1)
    current_deadlines = deadlines_db.get_deadlines_between(begin_time, end_time)

    if current_deadlines:
        LOGGER.info("Found deadlines for current minute.")
        SCHEDULER.remove_job('minutely_deadlines_check')  # Add actions for deadline
        for deadline in current_deadlines:
            task_id = deadline["task_id"]
            classroom_id = deadline["classroom_id"]

            classroom_info = classroom_db.get_info(classroom_id)
            task_info = None
            for task in classroom_info["tasks"]:
                if task["id"] == task_id:
                    task_info = task

            zip_dir_path = Path(get_temp_dir("auto")) / "tasks_packed"
            zip_file = pack_answers(classroom_id, task_id, zip_dir_path, classroom_db)

            for teacher_id in classroom_info["teachers"]:
                with open(zip_file, "rb") as handler:
                    await bot.send_message(teacher_id, "Hello, the deadline has finally come for your task with the "
                                                       f"description:\n<<{task_info['description']}>>")
                    await bot.send_message(teacher_id,
                                           "Here is a ZIP-archive with students' answers awailable at this moment."
                                           "Please, unpack it in single folder and do not rename the excel file. "
                                           "It has links to all students' answers and a mark column.\n"
                                           "After evaluating, please send me this excel file - just by the "
                                           "attachment button from the main menu.")
                    await bot.send_document(teacher_id, (f"task_{task_id}.zip", handler),
                                            reply_markup=await get_main_menu_markup("teacher"))
            for student_id in classroom_info["students"]:
                await bot.send_message(student_id, "Hello, the deadline has finally come for your task with the "
                                                   f"description:\n<<{task_info['description']}>>\n"
                                                   f"Your answers were already sent to teacher.\n"
                                                   f"You will receive a notification when your work is evaluated. "
                                                   f"Have a nice day!")

            task = Task(task_id, classroom_id)
            task.archive()


def pack_answers(classroom_id, task_id, destination_dir, classroom_db: ClassroomDatabase = None):
    """
    Generates ZIP-archive with structure: <id>/<files>, <id>/<files>, ..., gradebook.xlsx
    gradebook.xlsx is a MANAGER file with all the necessary links and grading column,
    which is necessary for further task processing.
    :param classroom_id:
    :param task_id:
    :param destination_dir:
    :param classroom_db:
    :return:
    """

    if not classroom_db:
        classroom_db = ClassroomDatabase()

    students_answers = {}
    students_tasks = {student["id"]: student["tasks"] for student in classroom_db.get_info(classroom_id)["students"]}
    for student_id, tasks in students_tasks.items():
        for task in tasks:
            if task["task_id"] == task_id:
                students_answers[student_id] = task
                break

    gradebook = xlsxwriter.Workbook(Path(destination_dir) / "temp" / f"gradebook-{task_id}.xlsx")
    worksheet = gradebook.add_worksheet()
    header_row = ["id", "answer_dir", "mark"]
    for col_num, data in enumerate(header_row):
        worksheet.write(0, col_num, data)

    row, col = 1, 0
    for student_id, task_data in students_answers.items():
        destination_root = Path(destination_dir) / "temp" / str(student_id)
        destination_root.mkdir(exist_ok=True, parents=True)
        with open(Path(destination_root / "description.txt"), "w+") as description_file:
            description_file.write(task_data["description"])
        for file in task_data["files"]:
            with open(Path(destination_root / file["filename"]), "wb+") as attachment_file:
                attachment_file.write(Binary(file["file"]))
        worksheet.write(row, col, str(student_id))
        worksheet.write_url(row, col + 1, f'external:{student_id}/', string="Click to open folder",
                            tip='TIP: Link will work only if this excel table is in the same dir '
                                'as students answers dirs (same folder structure as in archive).')
        row += 1
    gradebook.close()

    make_archive(Path(destination_dir) / f"{task_id}", "zip", Path(destination_dir) / "temp")
    rmtree(Path(destination_dir) / "temp")
    return Path(destination_dir) / f"{task_id}.zip"


class Task:
    """
    Task actions & some database interactions wrappers
    """

    def __init__(self, task_id, classroom_id,  # pylint: disable=too-many-arguments
                 classroom_db=None, user_db=None, deadlines_db=None):
        self._task_id = task_id
        self._classroom_id = classroom_id

        self._classroom_db: ClassroomDatabase = classroom_db or ClassroomDatabase()
        self._user_db: UserDatabase = user_db or UserDatabase()
        self._deadlines_db: DeadlineDatabase = deadlines_db or DeadlineDatabase()

        self._files = []
        self._description = "See attachments"

    def _get_array_id(self):
        """
        Get task id in classroom array
        :return: int
        """

        tasks = self._classroom_db.find_one({"classroom_id": self._classroom_id})["tasks"]
        for index, element in enumerate(tasks):
            if element["id"] == self._task_id:
                return index

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
        Activate/deactivate new tasks
        Warning: old tasks (after deadline) will be archived, NOT deactivated.
        Deactivated tasks are new tasks which have not been send tostudents yet.
        :param active:
        :return:
        """

        LOGGER.info(f"[Task] Trying to set activeness status: {active}")
        element_id = self._get_array_id()
        self._classroom_db.update({"classroom_id": self._classroom_id}, {f"tasks.{element_id}.active": active})

    def archive(self):
        """
        Make task archived after deadline and remove it from active tasks.
        :return:
        """

        LOGGER.info(f"[Task] Archiving task: {self._task_id}")
        tasks = self._classroom_db.find_one({"classroom_id": self._classroom_id})["tasks"]
        element_id = self._get_array_id()
        self._classroom_db.move_element({"classroom_id": self._classroom_id}, "tasks", element_id, "archived_tasks")

    def set_deadline(self, date: datetime):
        """
        Add/update task deadline

        :param date:
        :return:
        """

        LOGGER.info("[Task] Trying to update deadline")
        tasks = self._classroom_db.find_one({"classroom_id": self._classroom_id})["tasks"]
        element_id = self._get_array_id()
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

    def add_student_answer(self, student_id):
        """
        STUDENT task submission method
        :param student_id:
        :return:
        """

        LOGGER.info("Uploading task info to MongoDB")
        task_info = {
            "task_id": self._task_id,
            "files": self._files,
            "description": self._description
        }
        self._classroom_db.submit_task(student_id=student_id, classroom_id=self._classroom_id, info=task_info)

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
