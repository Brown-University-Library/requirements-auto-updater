"""
Module used by self_updater.py
Contains code for checking the target-project's environment.
"""

import json
import logging
import subprocess
from pathlib import Path

import dotenv

## set up logging ---------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(levelname)s [%(module)s-%(funcName)s()::%(lineno)d] %(message)s',
    datefmt='%d/%b/%Y %H:%M:%S',
)
log = logging.getLogger(__name__)


def validate_project_path(project_path: Path) -> None:
    """
    Validates that the provided project path exists.
    Exits the script if the path is invalid.
    """
    log.debug('starting validate_project_path()')
    log.debug(f'project_path: ``{project_path}``')
    if not project_path.exists():
        message = f'Error: The provided project_path ``{project_path}`` does not exist.'
        log.exception(message)
        raise Exception(message)
    else:
        log.debug('project_path exists')
    return


def determine_python_version(project_path: Path) -> str:
    """
    Determines Python version from the target-project's virtual environment.
    Exits the script if the virtual environment or Python version is invalid.
    """
    log.debug('starting infer_python_version()')
    env_python_path: Path = project_path.parent / 'env/bin/python3'
    if not env_python_path.exists():
        message = 'Error: Virtual environment not found.'
        log.exception(message)
        raise Exception(message)

    python_version: str = subprocess.check_output([str(env_python_path), '--version'], text=True).strip().split()[-1]
    if not python_version.startswith('3.'):
        message = 'Error: Invalid Python version.'
        log.exception(message)
        raise Exception(message)
    return python_version


def determine_environment_type() -> str:
    """
    Infers environment type based on the system hostname.
    Returns 'local', 'staging', or 'production'.
    """
    hostname: str = subprocess.check_output(['hostname'], text=True).strip()
    if hostname.startswith('d') or hostname.startswith('q'):
        env_type: str = 'staging'
    elif hostname.startswith('p'):
        env_type: str = 'production'
    else:
        env_type: str = 'local'
    log.debug(f'env_type: {env_type}')
    return env_type


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
        log.debug(f'uv_path: ``{uv_path}``')
    except subprocess.CalledProcessError:
        log.debug("`which` unsuccessful; accessing this script's venv")
        initial_uv_path: Path = Path(__file__).parent.parent / 'env' / 'bin' / 'uv'
        uv_path = initial_uv_path.resolve()
    log.debug(f'determined uv_path: ``{uv_path}``')
    return uv_path


def determine_email_addresses() -> list[list[str, str]]:
    """
    Loads email addresses from the target-project's `.env` file.
    Returns a list of email addresses.
    Assumes the setting `ADMINS_JSON` structured like:
    ADMINS_JSON='
    [
      [ "exampleFirstName exampleLastName", "example@domain.edu"],
      etc...
    ]'
    """
    log.debug('starting determine_email_addresses()')
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
        raise Exception(message)


def determine_group(project_path: Path) -> str:
    """
    Infers the group by examining existing files.
    Returns the most common group.
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
        raise Exception(message)
