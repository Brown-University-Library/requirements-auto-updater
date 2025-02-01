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
#     log.info('::: running initial tests ----------')
#     ## set the venv -------------------------------------------------
#     venv_tuple: tuple[Path, Path] = lib_common.determine_venv_paths(project_path)  # these are resolved-paths
#     (venv_bin_path, venv_path) = venv_tuple
#     local_scoped_env = make_local_scoped_env(project_path, venv_bin_path, venv_path)
#     ## prep the command ---------------------------------------------
#     command = make_run_tests_command(project_path, venv_bin_path)
#     ## run the command ----------------------------------------------
#     try:
#         subprocess.run(command, check=True, env=local_scoped_env)
#         log.info('ok / initial tests passed')
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
    log.info('::: running initial tests ----------')
    ## set the venv -------------------------------------------------
    venv_tuple: tuple[Path, Path] = lib_common.determine_venv_paths(project_path)  # these are resolved-paths
    (venv_bin_path, venv_path) = venv_tuple
    local_scoped_env: dict = make_local_scoped_env(project_path, venv_bin_path, venv_path)  # dict of envar-keys and paths
    ## prep the command ---------------------------------------------
    command: list[str] = make_run_tests_command(project_path, venv_bin_path)
    ## run the command ----------------------------------------------
    command_result: tuple[bool, dict] = run_run_tests_command(command, project_path, local_scoped_env)
    (ok, output) = command_result
    if not ok:
        message = f'Error on initial run_tests() call: ``{output}``. Halting self-update.'
        log.exception(message)
        ## email sys-admins -----------------------------------------
        emailer = Emailer(project_path)
        email_message: str = emailer.create_setup_problem_message(message)
        emailer.send_email(project_email_addresses, email_message)
        ## raise exception -----------------------------------------
        raise Exception(message)
    return


def run_run_tests_command(command: list, project_path: Path, local_scoped_env) -> tuple[bool, dict]:
    """
    Runs subprocess command and returns tuple (ok, data_dict).
    (Based on similar to `Go` style convention (err, data).)
    """
    result: subprocess.CompletedProcess = subprocess.run(
        command, cwd=str(project_path), env=local_scoped_env, capture_output=True, text=True
    )
    log.debug(f'result: {result}')
    ok = True if result.returncode == 0 else False
    if ok is True:
        log.info('ok / run_tests() passed')
    output = {'stdout': f'{result.stdout}', 'stderr': f'{result.stderr}'}
    return_val = (ok, output)
    log.debug(f'return_val: {return_val}')
    return return_val


# def run_git_push(project_path: Path) -> tuple[bool, dict]:
#     """
#     Runs `git push` and return the output.
#     """
#     log.info('::: running git push ----------')
#     command = ['git', 'push', 'origin', 'main']
#     result: subprocess.CompletedProcess = subprocess.run(command, cwd=str(project_path), capture_output=True, text=True)
#     log.debug(f'result: {result}')
#     ok = True if result.returncode == 0 else False
#     if ok is True:
#         if 'Everything up-to-date' in result.stderr:
#             log.info('ok / git push showed "Everything up-to-date"')
#         else:
#             log.info('ok / git push successful')
#     output = {'stdout': f'{result.stdout}', 'stderr': f'{result.stderr}'}
#     return_val = (ok, output)
#     log.debug(f'return_val: {return_val}')
#     return return_val


def run_followup_tests(uv_path: Path, project_path: Path, project_email_addresses: list[list[str, str]]) -> None | str:
    """
    Runs followup tests on the updated venv.

    If tests pass returns None.

    If tests fail:
    - returns "tests failed" message (to be add to the diff email)
    - does not exit, so that diffs can be emailed and permissions updated
    """
    log.info('::: running followup tests ----------')
    ## set the venv -------------------------------------------------
    venv_tuple: tuple[Path, Path] = lib_common.determine_venv_paths(project_path)  # these are resolved-paths
    (venv_bin_path, venv_path) = venv_tuple
    local_scoped_env = make_local_scoped_env(project_path, venv_bin_path, venv_path)
    ## prep the command ---------------------------------------------
    command = make_run_tests_command(project_path, venv_bin_path)
    ## run the command ----------------------------------------------
    try:
        subprocess.run(command, check=True, env=local_scoped_env)
        log.info('ok / followup tests passed')
        return_val = None
    except subprocess.CalledProcessError as e:
        message = f'Error on followup run_tests() call: ``{e}``.'
        log.exception(message)
        return_val = message
    log.debug(f'return_val, ``{return_val}``')
    return return_val


## helpers to the above main functions ------------------------------


def make_local_scoped_env(project_path: Path, venv_bin_path: Path, venv_path: Path) -> dict:
    """
    Creates a local-scoped environment for use in subprocess.run() calls.
    Called by run_initial_tests() and run_followup_tests().
    """
    local_scoped_env = os.environ.copy()
    local_scoped_env['PATH'] = f'{venv_bin_path}:{local_scoped_env["PATH"]}'  # prioritizes venv-path
    local_scoped_env['VIRTUAL_ENV'] = str(venv_path)
    log.debug(f'local_scoped_env, ``{local_scoped_env}``')
    return local_scoped_env


def make_run_tests_command(project_path: Path, venv_bin_path: Path) -> list[str]:
    """
    Prepares the run_tests command.
    Called by run_initial_tests() and run_followup_tests().
    """
    python_path = (
        venv_bin_path / 'python3'
    )  # don't resolve() -- venv_bin_path is already resolved; it'll use the system python-path and we want the venv python-path
    log.debug(f'python_path, ``{python_path}``')
    run_tests_path = project_path / 'run_tests.py'  # no need to resolve; project_path is already resolved
    command = [str(python_path), str(run_tests_path)]
    log.debug(f'command, ``{command}``')
    return command
