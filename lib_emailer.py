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
stuff_dir = this_file_path.parent.parent
dotenv_path = stuff_dir / '.env'
assert dotenv_path.exists(), f'file does not exist, ``{dotenv_path}``'
load_dotenv(find_dotenv(str(dotenv_path), raise_error_if_not_found=True), override=True)


log = logging.getLogger(__name__)


class Emailer:
    """
    Handles emailing updater-sys-admins and project-admins.
    """

    def __init__(self, project_path: Path) -> None:
        self.project_path: Path = project_path
        self.sys_admin_recipients: list = json.loads(os.environ['SLFUPDTR__SYS_ADMIN_RECIPIENTS_JSON'])
        self.self_updater_email_from: str = os.environ['SLFUPDTR__EMAIL_FROM']
        self.email_host: str = os.environ['SLFUPDTR__EMAIL_HOST']
        self.email_host_port: int = int(os.environ['SLFUPDTR__EMAIL_HOST_PORT'])
        self.server_name: str = socket.gethostname()

    def create_setup_problem_message(self, message: str) -> str:
        """
        Prepares problem-email message.
        The incoming `message` parameter is the error message from the exception that was raised.
        """
        log.debug('starting create_setup_problem_message()')
        email_message = f"""
        There was a problem running the self-updater script. 

        Message: ``{message}``.

        Suggestion, after fixing the problem, manually run the self-updater script again to make sure there aren't other environmental setup issues. 

        Usage instructions are at:
        <https://github.com/Brown-University-Library/self_updater_code?tab=readme-ov-file#usage>

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

        However, the post-update run_tests() failed -- and should be reviewed.
        
        The requirements.txt diff:\n\n{diff_text}.

        (end-of-message)
        """
        email_message: str = email_message.replace('        ', '')  # removes indentation-spaces
        return email_message

    def send_email(self, email_addresses: list[list[str, str]], message: str) -> None:
        """
        Builds and sends email.

        On a successful update email, the email_addresses will be the project-admins.
        On a setup problem email, the email_addresses will be the self-updater sys-admins.
        """
        log.debug('starting send_email_of_diffs()')
        log.debug(f'email_addresses: ``{email_addresses}``')
        ## prep email data ----------------------------------------------
        built_recipients = []
        for name, email in email_addresses:
            built_recipients.append(f'"{name}" <{email}>')
        log.debug(f'built_recipients: {built_recipients}')
        ## build email message ------------------------------------------
        eml = MIMEText(message)
        eml['Subject'] = f'bul-self-updater info from server``{self.server_name}`` for project ``{self.project_path.name}``'
        eml['From'] = self.self_updater_email_from
        eml['To'] = ', '.join(built_recipients)
        ## send email ---------------------------------------------------
        try:
            s = smtplib.SMTP(self.email_host, self.email_host_port)
            s.sendmail(self.self_updater_email_from, built_recipients, eml.as_string())
        except Exception as e:
            err = repr(e)
            log.exception(f'problem sending self-updater mail, ``{err}``')
            raise Exception(err)
        return

    ## end class Emailer
