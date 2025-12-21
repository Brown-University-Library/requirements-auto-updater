"""
This module provides two similarly structured test runners that wrap the same
"run tests" command for different phases of the auto-update workflow:

- run_initial_tests(uv_path, project_path, project_email_addresses):
  Runs the project's tests before any updates to validate that the environment
  is healthy and the script can proceed. On failure, emails project admins and
  raises an exception to halt the auto-update.

- run_followup_tests(uv_path, project_path):
  Runs the tests after the virtualenv has been updated. On failure, logs and
  returns a message so processing can continue without raising an exception (e.g., emailing diffs and
  updating permissions).
"""

import logging
import subprocess
from pathlib import Path

from lib.lib_emailer import Emailer

log = logging.getLogger(__name__)


def run_initial_tests(uv_path: Path, project_path: Path, project_email_addresses: list[tuple[str, str]]) -> None:
    """
    Run initial tests to ensure that the script can run.

    On failure:
    - Emails project-admins
    - Raises an exception
    """
    log.info('::: running initial tests ----------')
    ## prep the command ---------------------------------------------
    command: list[str] = make_run_tests_command(project_path, uv_path)
    ## run the command ----------------------------------------------
    command_result: tuple[bool, dict] = run_run_tests_command(command, project_path)
    (ok, output) = command_result
    if not ok:
        message = f'Error on initial run_tests() call: ``{output}``. Halting auto-update.'
        log.exception(message)
        ## email sys-admins -----------------------------------------
        emailer = Emailer(project_path)
        email_message: str = emailer.create_setup_problem_message(message)
        emailer.send_email(project_email_addresses, email_message)
        ## raise exception -----------------------------------------
        raise Exception(message)
    else:
        log.info('ok / initial tests passed')
    return


def run_followup_tests(uv_path: Path, project_path: Path) -> None | str:
    """
    Runs followup tests on the updated venv.

    If tests pass returns None.

    If tests fail:
    - returns "tests failed" message (to be add to the diff email)
    - does not exit, so that diffs can be emailed and permissions updated
    """
    log.info('::: running followup tests ----------')
    ## prep the command ---------------------------------------------
    command: list[str] = make_run_tests_command(project_path, uv_path)
    ## run the command ----------------------------------------------
    command_result: tuple[bool, dict] = run_run_tests_command(command, project_path)
    (ok, output) = command_result
    if not ok:
        return_val = f'Error on followup run_tests() call: ``{output}``. Continuing processing to update permissions.'
        log.exception(return_val)
    else:
        log.info('ok / followup tests passed')
        return_val = None
    log.debug(f'return_val, ``{return_val}``')
    return return_val


def make_run_tests_command(project_path: Path, uv_path: Path) -> list[str]:
    """
    Prepares the run_tests command.
    Called by run_initial_tests() and run_followup_tests().
    """
    run_tests_path = project_path / 'run_tests.py'  # no need to resolve; project_path is already resolved
    command = [str(uv_path), 'run', str(run_tests_path)]
    log.debug(f'command, ``{command}``')
    return command


def run_run_tests_command(command: list, project_path: Path) -> tuple[bool, dict]:
    """
    Runs subprocess command and returns tuple (ok, data_dict).
    (Based on similar to `Go` style convention (err, data).)
    Called by run_initial_tests() and run_followup_tests().
    """
    log.debug(f'running with cwd arg, ``{project_path}``')
    result: subprocess.CompletedProcess = subprocess.run(command, cwd=str(project_path), capture_output=True, text=True)
    log.debug(f'result: {result}')
    ok = True if result.returncode == 0 else False
    output = {'stdout': f'{result.stdout}', 'stderr': f'{result.stderr}'}
    return_val = (ok, output)
    log.debug(f'return_val: {return_val}')
    return return_val


# def run_initial_tests(uv_path: Path, project_path: Path, project_email_addresses: list[tuple[str, str]]) -> None:
#     """
#     Run initial tests to ensure that the script can run.

#     On failure:
#     - Emails project-admins
#     - Raises an exception
#     """
#     log.info('::: running initial tests ----------')
#     ## set the venv -------------------------------------------------
#     venv_tuple: tuple[Path, Path] = lib_common.determine_venv_paths(project_path)  # these are resolved-paths
#     (venv_bin_path, venv_path) = venv_tuple
#     local_scoped_env: dict = make_local_scoped_env(project_path, venv_bin_path, venv_path)  # dict of envar-keys and paths
#     ## prep the command ---------------------------------------------
#     command: list[str] = make_run_tests_command(project_path, venv_bin_path)
#     ## run the command ----------------------------------------------
#     command_result: tuple[bool, dict] = run_run_tests_command(command, project_path, local_scoped_env)
#     (ok, output) = command_result
#     if not ok:
#         message = f'Error on initial run_tests() call: ``{output}``. Halting auto-update.'
#         log.exception(message)
#         ## email sys-admins -----------------------------------------
#         emailer = Emailer(project_path)
#         email_message: str = emailer.create_setup_problem_message(message)
#         emailer.send_email(project_email_addresses, email_message)
#         ## raise exception -----------------------------------------
#         raise Exception(message)
#     else:
#         log.info('ok / initial tests passed')
#     return


# def run_followup_tests(uv_path: Path, project_path: Path) -> None | str:
#     """
#     Runs followup tests on the updated venv.

#     If tests pass returns None.

#     If tests fail:
#     - returns "tests failed" message (to be add to the diff email)
#     - does not exit, so that diffs can be emailed and permissions updated
#     """
#     log.info('::: running followup tests ----------')
#     ## set the venv -------------------------------------------------
#     venv_tuple: tuple[Path, Path] = lib_common.determine_venv_paths(project_path)  # these are resolved-paths
#     (venv_bin_path, venv_path) = venv_tuple
#     local_scoped_env: dict = make_local_scoped_env(project_path, venv_bin_path, venv_path)
#     ## prep the command ---------------------------------------------
#     command: list[str] = make_run_tests_command(project_path, venv_bin_path)
#     ## run the command ----------------------------------------------
#     command_result: tuple[bool, dict] = run_run_tests_command(command, project_path, local_scoped_env)
#     (ok, output) = command_result
#     if not ok:
#         return_val = f'Error on followup run_tests() call: ``{output}``. Continuing processing to update permissions.'
#         log.exception(return_val)
#     else:
#         log.info('ok / followup tests passed')
#         return_val = None
#     log.debug(f'return_val, ``{return_val}``')
#     return return_val


## helpers to the above main functions ------------------------------


# def make_local_scoped_env(project_path: Path, venv_bin_path: Path, venv_path: Path) -> dict:
#     """
#     Creates a local-scoped environment for use in subprocess.run() calls.
#     Called by run_initial_tests() and run_followup_tests().
#     """
#     local_scoped_env = os.environ.copy()
#     local_scoped_env['PATH'] = f'{venv_bin_path}:{local_scoped_env["PATH"]}'  # prioritizes venv-path
#     local_scoped_env['VIRTUAL_ENV'] = str(venv_path)
#     log.debug(f'local_scoped_env, ``{local_scoped_env}``')
#     return local_scoped_env


# def make_run_tests_command(project_path: Path, venv_bin_path: Path) -> list[str]:
#     """
#     Prepares the run_tests command.
#     Called by run_initial_tests() and run_followup_tests().
#     Note: we're NOT calling resolve() on the python_path.
#         The venv_bin_path is already resolved, so this will use the venv python-path, which we want.
#         Resolving again would use the system python-path, which we do not want.
#     """
#     python_path = venv_bin_path / 'python3'  # no need to resolve; see docstring note above
#     log.debug(f'python_path, ``{python_path}``')
#     run_tests_path = project_path / 'run_tests.py'  # no need to resolve; project_path is already resolved
#     command = [str(python_path), str(run_tests_path)]
#     log.debug(f'command, ``{command}``')
#     return command
