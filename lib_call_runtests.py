import logging
import subprocess
from pathlib import Path

from lib_emailer import Emailer

log = logging.getLogger(__name__)


def run_initial_tests(uv_path: Path, project_path: Path, project_email_addresses: list[list[str, str]]) -> None:
    """
    Run initial tests to ensure that the script can run.

    On failure:
    - Emails project-admins
    - Raises an exception
    """
    log.debug('starting run_initial_tests()')
    run_tests_initial_path = project_path / 'run_tests.py'
    run_tests_path = run_tests_initial_path.resolve()
    try:
        command = [str(uv_path), 'run', str(run_tests_path)]
        log.debug(f'command: ``{command}``')
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError:
        message = 'Errors on initial test-run. Halting self-update.'
        log.exception(message)
        ## email sys-admins -----------------------------------------
        emailer = Emailer(project_path)
        email_message: str = emailer.create_setup_problem_message(message)
        emailer.send_email(project_email_addresses, email_message)
        ## raise exception -----------------------------------------
        raise Exception(message)
    return


def run_followup_tests(uv_path: Path, project_path: Path) -> None | str:
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
    except subprocess.CalledProcessError:
        message = 'tests failed after updating venv'
        log.exception(message)
        return_val = message
    return return_val
