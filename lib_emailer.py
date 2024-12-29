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


## prepare logger ---------------------------------------------------
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

    def create_setup_problem_message(self, message: str) -> str:
        """
        Prepares problem-email.
        The incoming `message` parameter is the error message from the exception that was raised.
        """
        log.debug('starting create_setup_problem_message()')
        email_message = f'''
There was a problem running the self-updater script. 

Message: ``{message}``.

Suggestion, after fixing the problem, manually run the self-updater script again to make 
sure there aren't other environmental setup issues. 

Usage instructions are at:
<https://github.com/Brown-University-Library/self_updater_code?tab=readme-ov-file#usage>
'''
        return email_message

    def send_email(self, email_addresses: list[list[str, str]], message: str) -> None:
        """
        Sends an email with the differences between the previous and current requirements files.
        """
        log.debug('starting send_email_of_diffs()')
        log.debug(f'email_addresses: ``{email_addresses}``')
        ## prep email data ----------------------------------------------
        recipients = []
        for name, email in email_addresses:
            recipients.append(f'"{name}" <{email}>')
        log.debug(f'recipients: {recipients}')
        EMAIL_RECIPIENTS: list = recipients
        HOST: str = socket.gethostname()
        log.debug( f'HOST, ``{HOST}``; self.email_host, ``{self.email_host}``; which do I want?' )
        ## build email message ------------------------------------------
        eml = MIMEText(message)
        eml['Subject'] = f'bul-self-updater info from ``{HOST.upper()}`` for project ``{self.project_path.name}``'
        eml['From'] = self.self_updater_email_from
        eml['To'] = ', '.join(EMAIL_RECIPIENTS)
        ## send email ---------------------------------------------------
        try:
            s = smtplib.SMTP(self.`email_host`, self.email_host_port)
            s.sendmail(self.self_updater_email_from, EMAIL_RECIPIENTS, eml.as_string())
        except Exception as e:
            err = repr(e)
            log.exception(f'problem sending self-updater mail, ``{err}``')
            raise Exception(err)
        return

    ## end class Emailer
