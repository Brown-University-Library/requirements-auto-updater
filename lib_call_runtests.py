import logging
import os
import subprocess
from pathlib import Path

import lib_common
from lib_emailer import Emailer

log = logging.getLogger(__name__)


# def run_initial_tests(uv_path: Path, project_path: Path, project_email_addresses: list[list[str, str]]) -> None:
#     """
#     Run initial tests to ensure that the script can run.

#     On failure:
#     - Emails project-admins
#     - Raises an exception
#     """
#     log.debug('starting run_initial_tests()')
#     run_tests_initial_path = project_path / 'run_tests.py'
#     run_tests_path = run_tests_initial_path.resolve()
#     try:
#         command = [str(uv_path), 'run', str(run_tests_path)]
#         log.debug(f'command: ``{command}``')
#         subprocess.run(command, check=True)
#     except Exception as e:
#         message = f'Error on initial run_tests() call: ``{e}``. Halting self-update.'
#         log.exception(message)
#         ## email sys-admins -----------------------------------------
#         emailer = Emailer(project_path)
#         email_message: str = emailer.create_setup_problem_message(message)
#         emailer.send_email(project_email_addresses, email_message)
#         ## raise exception -----------------------------------------
#         raise Exception(message)
#     return


def run_initial_tests(uv_path: Path, project_path: Path, project_email_addresses: list[list[str, str]]) -> None:
    """
    Run initial tests to ensure that the script can run.

    On failure:
    - Emails project-admins
    - Raises an exception
    """
    log.debug('starting run_initial_tests()')
    ## set the venv -------------------------------------------------
    venv_tuple: tuple[Path, Path] = lib_common.determine_venv_paths(project_path)  # these are resolved-paths
    (venv_bin_path, venv_path) = venv_tuple
    local_scoped_env = os.environ.copy()
    local_scoped_env['PATH'] = f'{venv_bin_path}:{local_scoped_env["PATH"]}'  # prioritizes venv-path
    local_scoped_env['VIRTUAL_ENV'] = str(venv_path)
    ## prep the command ---------------------------------------------
    python_path = (
        venv_bin_path / 'python3'
    )  # don't resolve() -- venv_bin_path is already resolved; it'll use the system python-path and we want the venv python-path
    log.debug(f'python_path, ``{python_path}``')
    run_tests_path = project_path / 'run_tests.py'  # no need to resolve; project_path is already resolved
    command = [str(python_path), str(run_tests_path)]
    log.debug(f'initial runtests command: ``{command}``')
    ## run the command ----------------------------------------------
    try:
        subprocess.run(command, check=True, env=local_scoped_env)
    except Exception as e:
        message = f'Error on initial run_tests() call: ``{e}``. Halting self-update.'
        log.exception(message)
        ## email sys-admins -----------------------------------------
        emailer = Emailer(project_path)
        email_message: str = emailer.create_setup_problem_message(message)
        emailer.send_email(project_email_addresses, email_message)
        ## raise exception -----------------------------------------
        raise Exception(message)
    return


def run_followup_tests(uv_path: Path, project_path: Path, project_email_addresses: list[list[str, str]]) -> None | str:
    """
    Runs followup tests on the updated venv.

    If tests pass returns None.

    If tests fail:
    - returns "tests failed" message (to be add to the diff email)
    - does not exit, so that diffs can be emailed and permissions updated
    """
    log.debug('starting run_followup_tests()')
    run_tests_initial_path = project_path / 'run_tests.py'
    run_tests_path = run_tests_initial_path.resolve()
    try:
        command = [str(uv_path), 'run', str(run_tests_path)]
        log.debug(f'command: ``{command}``')
        subprocess.run(command, check=True)
        return_val = None
    except subprocess.CalledProcessError as e:
        message = f'Error on followup run_tests() call: ``{e}``.'
        log.exception(message)
        return_val = message
    return return_val
