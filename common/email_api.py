"""
Email work tools
"""

import smtplib

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

from configs.bot_conf import BotConfig
from configs.logger_conf import configure_logger


LOGGER = configure_logger(__name__)


def send_mail(mail_to, subject, text_message, attachments=None) -> bool:
    """
    Send email to user

    :param mail_to: str or list of receivers
    :param subject: str
    :param text_message: str
    :param attachments: list of dicts {"filename": name, "file": Binary}
    :return:
    """

    mail_params = BotConfig().properties.get("MAIL", None)
    if not mail_params:
        LOGGER.error("Could not get mail info from bot configuration.")
        return False
    if not isinstance(mail_to, list):
        mail_to = [mail_to]

    server = smtplib.SMTP_SSL(mail_params["SERVER"], mail_params["PORT"])
    server.login(mail_params["ADDRESS"], mail_params["PASSWORD"])

    email_message = MIMEMultipart()
    email_message.attach(MIMEText(text_message))
    email_message["From"] = mail_params["ADDRESS"]
    email_message["To"] = ",".join(mail_to)
    email_message["Subject"] = subject

    for attachment in attachments:
        part = MIMEApplication(
            attachment["file"],
            Name=attachment["filename"]
        )
        part["Content-Disposition"] = f'attachment; filename="{attachment["filename"]}"'
        email_message.attach(part)

    server.sendmail(mail_params["ADDRESS"], mail_to, email_message.as_string())
    server.close()

    return True
