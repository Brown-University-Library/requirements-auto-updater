"""
TODO: remove dotenv dependency, and pass in necessary data to Emailer constructor.
"""

import json
import logging
import os
import smtplib
import socket
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

## load envars ------------------------------------------------------
this_file_path = Path(__file__).resolve()
stuff_dir = this_file_path.parent.parent.parent
dotenv_path = stuff_dir / '.env'
assert dotenv_path.exists(), f'file does not exist, ``{dotenv_path}``'
load_dotenv(find_dotenv(str(dotenv_path), raise_error_if_not_found=True), override=True)


log = logging.getLogger(__name__)


def send_email_of_diffs(
    project_path: Path, diff_text: str, followup_problems: dict, project_email_addresses: list[tuple[str, str]]
) -> None:
    """
    Manages the sending of an email with the differences between the previous and current requirements files.

    If the followup copy-new-requirements.in file or run-tests failed, a note to that effect will be included in the email.

    Note that on an email-send error, the error will be logged, but the script will continue,
      so the permissions-update will still occur.

    Called by: auto_updater.manage_update()
    """
    ## prepare problem-message --------------------------------------
    log.info('::: preparing problem-message ----------')
    problem_message: str = ''
    if followup_problems['collectstatic_problems']:
        problem_message = followup_problems['collectstatic_problems']
    if followup_problems['test_problems']:
        if problem_message:
            problem_message += '\n\n'
        problem_message += followup_problems['test_problems']
    if problem_message:
        log.info(f'ok / problem_message, ``{problem_message}``')
    else:
        log.info('ok / no problem_message')
    ## send email ---------------------------------------------------
    emailer = Emailer(project_path)
    if problem_message:
        email_message: str = emailer.create_update_problem_message(diff_text, problem_message)
    else:
        email_message: str = emailer.create_update_ok_message(diff_text)
    try:
        emailer.send_email(project_email_addresses, email_message)
    except Exception:
        message = 'problem sending email'
        log.exception(message)
    return


class Emailer:
    """
    Handles emailing updater-sys-admins and project-admins.
    """

    def __init__(self, project_path: Path) -> None:
        self.project_path: Path = project_path
        self.sys_admin_recipients: list = json.loads(os.environ['AUTO_UPDTR__SYS_ADMIN_RECIPIENTS_JSON'])
        self.auto_updater_email_from: str = os.environ['AUTO_UPDTR__EMAIL_FROM']
        self.email_host: str = os.environ['AUTO_UPDTR__EMAIL_HOST']
        self.email_host_port: int = int(os.environ['AUTO_UPDTR__EMAIL_HOST_PORT'])
        self.server_name: str = socket.gethostname()

    def create_setup_problem_message(self, message: str) -> str:
        """
        Prepares problem-email message.
        The incoming `message` parameter is the error message from the exception that was raised.
        """
        log.debug('starting create_setup_problem_message()')
        email_message = f"""
        There was a problem running the auto-updater script. 

        Message: ``{message}``.

        Suggestion, after fixing the problem, manually run the auto-updater script again to make sure there aren't other environmental setup issues. 

        Usage instructions are at:
        <https://github.com/Brown-University-Library/requirements-auto-updater?tab=readme-ov-file#usage>

        (end-of-message)
        """
        email_message: str = email_message.replace('        ', '')  # removes indentation-spaces
        return email_message

    def create_update_ok_message(self, diff_text: str) -> str:
        """
        Prepares update-ok email message.
        Includes the differences between the previous and current requirements.
        """
        log.debug('starting create_update_ok_message()')
        email_message = f"""
        The venv for the project ``{self.project_path.name}`` has been auto-updated successfully. 
        
        The requirements.txt diff:\n\n{diff_text}.

        (end-of-message)
        """
        email_message: str = email_message.replace('        ', '')  # removes indentation-spaces
        return email_message

    def create_update_problem_message(self, diff_text: str, followup_test_problems: str) -> str:
        """
        Prepares "update-happened, but there are post-update test failures" email message.
        Includes the differences between the previous and current requirements.
        """
        log.debug('starting create_update_problem_message()')
        email_message = f"""
        The venv for the project ``{self.project_path.name}`` has been auto-updated and is active. 

        However, there were post-update problems which should be reviewed:
        {followup_test_problems}
        
        The requirements.txt diff:\n\n{diff_text}.

        (end-of-message)
        """
        email_message: str = email_message.replace('        ', '')  # removes indentation-spaces
        return email_message

    def truncate_long_lines(self, message: str, max_length: int = 950) -> str:
        """
        Handles error: `smtplib.SMTPDataError: (500, b'Line too long (see RFC5321 4.5.3.1.6)')` by truncating long lines
        """
        truncated_lines = []
        for line in message.splitlines():
            if len(line) > max_length:
                truncated_lines.append(line[:max_length] + '... [truncated]')
            else:
                truncated_lines.append(line)
        return '\n'.join(truncated_lines)

    def send_email(self, email_addresses: list[tuple[str, str]], message: str) -> None:
        """
        Builds and sends email.

        On a successful update email, the email_addresses will be the project-admins.
        On a setup problem email, the email_addresses will be the auto-updater sys-admins.
        """
        log.info('::: sending email ----------')
        log.debug(f'email_addresses: ``{email_addresses}``')
        ## prep email data ----------------------------------------------
        built_recipients = []
        for name, email in email_addresses:
            built_recipients.append(f'"{name}" <{email}>')
        log.debug(f'built_recipients: {built_recipients}')
        ## build email message ------------------------------------------
        valid_message: str = self.truncate_long_lines(message)  # email spec limits lines to 1000 characters
        eml = MIMEText(valid_message)
        eml['Subject'] = f'bul-auto-updater info from server ``{self.server_name}`` for project ``{self.project_path.name}``'
        eml['From'] = self.auto_updater_email_from
        eml['To'] = ', '.join(built_recipients)
        ## send email ---------------------------------------------------
        try:
            s = smtplib.SMTP(self.email_host, self.email_host_port)
            s.sendmail(self.auto_updater_email_from, built_recipients, eml.as_string())
            log.info('ok / email sent')
        except Exception as e:
            err = repr(e)
            log.exception(f'problem sending auto-updater mail, ``{err}``')
            raise Exception(err)
        return

    ## end class Emailer
