"""
Module used by self_updater.py
Contains code for checking the target-project's environment.
"""

import json
import logging
import subprocess
from pathlib import Path

import dotenv

import lib_git_handler
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


def check_branch(project_path, project_email_addresses) -> None:
    """
    Checks that the project is on the `main` branch.
    If not, sends an email to the project sys-admins, then exits.
    """
    branch = fetch_branch_data(project_path)
    if branch != 'main':
        message = f'Error: Project is on branch ``{branch}`` instead of ``main``'
        log.exception(message)
        ## email project sys-admins ---------------------------------
        emailer = Emailer(project_path)
        email_message: str = emailer.create_setup_problem_message(message)
        emailer.send_email(project_email_addresses, email_message)
        ## raise exception -----------------------------------------
        raise Exception(message)


def fetch_branch_data(project_path: Path) -> str:
    """
    Fetches branch-data by reading the `.git/HEAD` file (avoiding calling git via subprocess due to `dubious ownership` issue).
    Called by check_branch()
    """
    log.debug('starting fetch_branch_data')
    git_dir = project_path / '.git'
    try:
        ## read HEAD file to find the project branch ------------
        head_file = git_dir / 'HEAD'
        ref_line = head_file.read_text().strip()
        if ref_line.startswith('ref:'):
            project_branch = ref_line.split('/')[-1]  # extract the project_branch name
        else:
            project_branch = 'detached'
    except FileNotFoundError:
        log.warning('no `.git` directory or HEAD file found.')
        project_branch = 'project_branch_not_found'
    except Exception:
        log.exception('other problem fetching project_branch data')
        project_branch = 'project_branch_not_found'
    log.debug(f'project_branch: ``{project_branch}``')
    return project_branch


def check_git_status(project_path: Path, project_email_addresses: list[list[str, str]]) -> None:
    """
    Checks that the project has no uncommitted changes.
    If there are uncommitted changes:
    - Sends an email to the project sys-admins
    - Exits the script

    Note: just looking for the word 'clean' because one version of git says "working tree clean"
        and another says "working directory clean". TODO: consider just checking the ok boolean.
    """
    log.debug('starting check_git_status()')
    ## check for uncommitted changes --------------------------
    call_result: tuple[bool, dict] = lib_git_handler.run_git_status(project_path)
    (ok, output) = call_result
    if 'clean' not in output['stdout']:
        message = 'Error: git-status check failed.'
        log.exception(message)
        ## email project sys-admins ---------------------------------
        emailer = Emailer(project_path)
        email_message: str = emailer.create_setup_problem_message(message)
        emailer.send_email(project_email_addresses, email_message)
        ## raise exception -----------------------------------------
        raise Exception(message)
    return


def determine_python_version(project_path: Path, project_email_addresses: list[list[str, str]]) -> tuple[str, str, str]:
    """
    Determines Python version from the target-project's virtual environment.
    The purpose is to later run the `uv pip compile ...` command, to add the --python version

    If the virtual environment or python version is invalid:
    - Sends an email to the project sys-admins
    - Exits the script

    Of the returned info, only the resolved-python-path is currently used.

    History:
    - Initially I just grabbed the python version.
    - But `uv pip compile ... --python version` could fail if uv didn't find that python version.
    - I thought the tilde-notation would resolve this, but it didn't.
    - Grabbing the actual resolved-path to the venv's python executable works.

    TODO: eventually remove the unneed code.
    """
    log.debug('starting determine_python_version()')
    ## get env_python_path ------------------------------------------
    env_python_path: Path = project_path.parent / 'env/bin/python3'
    log.debug(f'env_python_path before resolve: ``{env_python_path}``')
    if not env_python_path.exists():
        message = 'Error: Virtual environment not found.'
        log.exception(message)
        ## email project sys-admins ---------------------------------
        emailer = Emailer(project_path)
        email_message: str = emailer.create_setup_problem_message(message)
        emailer.send_email(project_email_addresses, email_message)
        ## raise exception -----------------------------------------
        raise Exception(message)
    ## get version --------------------------------------------------
    python_version: str = subprocess.check_output([str(env_python_path), '--version'], text=True).strip().split()[-1]
    log.debug(f'python_version: {python_version}')
    ## tildify version ----------------------------------------------
    parts: list = python_version.split('.')
    tilde_notation: str = f'~={parts[0]}.{parts[1]}.0'  # converts, eg, '3.8.10' to '~=3.8.0'
    log.debug(f'tilde_notation: {tilde_notation}')
    ## resolve env_python_path --------------------------------------
    env_python_path_resolved: str = str(env_python_path.resolve())  # only this is used by the calling code
    log.debug(f'env_python_path_resolved: ``{env_python_path_resolved}``')
    ## confirm Python 3 ---------------------------------------------
    if not python_version.startswith('3.'):
        message = 'Error: Invalid Python version.'
        log.exception(message)
        ## email project-admins -------------------------------------
        emailer = Emailer(project_path)
        email_message: str = emailer.create_setup_problem_message(message)
        emailer.send_email(project_email_addresses, email_message)
        ## raise exception -----------------------------------------
        raise Exception(message)
    return (python_version, tilde_notation, env_python_path_resolved)

    ## end def determine_python_version()


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
