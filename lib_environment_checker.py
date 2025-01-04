"""
Module used by self_updater.py
Contains code for checking the target-project's environment.
"""

import json
import logging
import subprocess
from pathlib import Path

import dotenv

from lib_emailer import Emailer

log = logging.getLogger(__name__)


def validate_project_path(project_path: Path) -> None:
    """
    Validates that the provided project path exists.
    If path is invalid:
    - Sends an email to the self-updater sys-admins
    - Exits the script
    """
    log.debug('starting validate_project_path()')
    log.debug(f'project_path: ``{project_path}``')
    if not project_path.exists():
        message = f'Error: The provided project_path ``{project_path}`` does not exist. Halting self-update.'
        log.exception(message)
        ## email project sys-admins ---------------------------------
        emailer = Emailer(project_path)
        email_message: str = emailer.create_setup_problem_message(message)
        emailer.send_email(emailer.sys_admin_recipients, email_message)
        ## raise exception -----------------------------------------
        raise Exception(message)
    else:
        log.debug('project_path valid')
    return


def determine_project_email_addresses(project_path: Path) -> list[list[str, str]]:
    """
    Loads email addresses from the target-project's `.env` file.
    Returns a list of email addresses.
    Assumes the setting `ADMINS_JSON` structured like:
    ADMINS_JSON='
    [
      [ "exampleFirstName exampleLastName", "example@domain.edu"],
      etc...
    ]'

    If there's an error:
    - Sends an email to the self-updater sys-admins
    - Exits the script
    """
    log.debug('starting determine_project_email_addresses()')
    try:
        settings: dict = dotenv.dotenv_values('../.env')
        # email_addresses: list[list[str, str]] = settings['ADMINS_JSON']
        email_addresses_json: str = settings['ADMINS_JSON']
        email_addresses: list[list[str, str]] = json.loads(email_addresses_json)
        log.debug(f'email_addresses: {email_addresses}')
        log.debug(f'type(email_addresses): {type(email_addresses)}')
        return email_addresses
    except Exception as e:
        message = f'Error determining email addresses: {e}'
        log.exception(message)
        ## email project sys-admins ---------------------------------
        emailer = Emailer(project_path)
        email_message: str = emailer.create_setup_problem_message(message)
        emailer.send_email(emailer.sys_admin_recipients, email_message)
        ## raise exception -----------------------------------------
        raise Exception(message)

    ## end def determine_project_email_addresses()


def determine_python_version(project_path: Path, project_email_addresses: list[list[str, str]]) -> tuple[str, str]:
    """
    Determines Python version from the target-project's virtual environment.

    If the virtual environment or python version is invalid:
    - Sends an email to the project sys-admins
    - Exits the script
    """
    log.debug('starting infer_python_version()')
    env_python_path: Path = project_path.parent / 'env/bin/python3'
    if not env_python_path.exists():
        message = 'Error: Virtual environment not found.'
        log.exception(message)
        ## email project sys-admins ---------------------------------
        emailer = Emailer(project_path)
        email_message: str = emailer.create_setup_problem_message(message)
        emailer.send_email(project_email_addresses, email_message)
        ## raise exception -----------------------------------------
        raise Exception(message)
    python_version: str = subprocess.check_output([str(env_python_path), '--version'], text=True).strip().split()[-1]
    log.debug(f'python_version: {python_version}')
    ## tildify ------------------------------------------------------
    parts: list = python_version.split('.')
    tilde_notation: str = f'~={parts[0]}.{parts[1]}.0'  # converts, eg, '3.8.10' to '~=3.8.0'
    log.debug(f'tilde_notation: {tilde_notation}')
    if not python_version.startswith('3.'):
        message = 'Error: Invalid Python version.'
        log.exception(message)
        ## email project-admins -------------------------------------
        emailer = Emailer(project_path)
        email_message: str = emailer.create_setup_problem_message(message)
        emailer.send_email(project_email_addresses, email_message)
        ## raise exception -----------------------------------------
        raise Exception(message)
    return (python_version, tilde_notation)


def determine_environment_type(project_path: Path, project_email_addresses: list[list[str, str]]) -> str:
    """
    Infers environment type based on the system hostname.
    Returns 'local', 'staging', or 'production'.
    """
    ## ensure all .in files exist -----------------------------------
    for filename in ['local.in', 'staging.in', 'production.in']:
        full_path: Path = project_path / 'requirements' / filename
        try:
            assert full_path.exists()
        except AssertionError:
            message = f'Error: {full_path} not found'
            log.exception(message)
            ## email project-admins ---------------------------------
            emailer = Emailer(project_path)
            email_message: str = emailer.create_setup_problem_message(message)
            emailer.send_email(project_email_addresses, email_message)
            ## raise exception --------------------------------------
            raise Exception(message)
    ## determine proper one -----------------------------------------
    hostname: str = subprocess.check_output(['hostname'], text=True).strip().lower()
    if hostname.startswith('d') or hostname.startswith('q'):
        env_type: str = 'staging'
    elif hostname.startswith('p'):
        env_type: str = 'production'
    else:
        env_type: str = 'local'
    log.debug(f'env_type: {env_type}')
    return env_type


# def determine_environment_type() -> str:
#     """
#     Infers environment type based on the system hostname.
#     Returns 'local', 'staging', or 'production'.
#     """
#     hostname: str = subprocess.check_output(['hostname'], text=True).strip()
#     if hostname.startswith('d') or hostname.startswith('q'):
#         env_type: str = 'staging'
#     elif hostname.startswith('p'):
#         env_type: str = 'production'
#     else:
#         env_type: str = 'local'
#     log.debug(f'env_type: {env_type}')
#     return env_type


def determine_uv_path() -> Path:
    """
    Checks `which` for the `uv` command.
    If that fails, gets path from this script's venv.
    Used for compile and sync.
    """
    log.debug('starting determine_uv_path()')
    try:
        uv_initial_path: str = subprocess.check_output(['which', 'uv'], text=True).strip()
        uv_path = Path(uv_initial_path).resolve()  # to ensure an absolute-path
    except subprocess.CalledProcessError:
        log.debug("`which` unsuccessful; accessing this script's venv")
        initial_uv_path: Path = Path(__file__).parent.parent / 'env' / 'bin' / 'uv'
        uv_path = initial_uv_path.resolve()
    log.debug(f'determined uv_path: ``{uv_path}``')
    return uv_path


def determine_group(project_path: Path, project_email_addresses: list[list[str, str]]) -> str:
    """
    Infers the group by examining existing files.
    Returns the most common group.

    If there's an error:
    - Sends an email to the project sys-admins
    - Exits the script
    """
    log.debug('starting infer_group()')
    try:
        group_list: list[str] = subprocess.check_output(['ls', '-l', str(project_path)], text=True).splitlines()
        groups = [line.split()[3] for line in group_list if len(line.split()) > 3]
        most_common_group: str = max(set(groups), key=groups.count)
        log.debug(f'most_common_group: {most_common_group}')
        return most_common_group
    except Exception as e:
        message = f'Error inferring group: {e}'
        log.exception(message)
        ## email sys-admins -----------------------------------------
        emailer = Emailer(project_path)
        email_message: str = emailer.create_setup_problem_message(message)
        emailer.send_email(project_email_addresses, email_message)
        ## raise exception -----------------------------------------
        raise Exception(message)
