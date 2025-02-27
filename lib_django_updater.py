import logging
import os
import pprint
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def check_for_django_update(incoming_text: str) -> bool:
    """
    Checks if incoming diff-text indicates a django update.

    Iterates through lines of incoming text.
    - first strips whitespace from each line
    - then checks if the string '+django==' is in the line
    """
    log.info('::: check_for_django_update ----------')
    return_val: bool = False
    incoming_lines: list = incoming_text.split('\n')
    for line in incoming_lines:
        line: str = line.strip()
        if '+django==' in line:
            return_val = True
            break
    log.info(f'ok / django-updated, ``{return_val}``')
    return return_val


def run_collectstatic(project_path: Path) -> None | str:
    """
    Runs collectstatic command.
    """
    log.info('::: running collectstatic ----------')
    log.debug(f'cwd: {os.getcwd()}')
    command = ['bash', '-c', 'source ../env/bin/activate && python ./manage.py collectstatic --noinput']
    log.debug(f'command: {command}')
    # subprocess.run(command, check=True)
    result: subprocess.CompletedProcess = subprocess.run(command, cwd=str(project_path), capture_output=True, text=True)
    log.debug(f'result: {result}')
    ok = True if result.returncode == 0 else False
    if ok is True:
        log.info('ok / collectstatic successful')
        problem_message = None
    else:
        output = {'stdout': f'{result.stdout}', 'stderr': f'{result.stderr}'}
        problem_message = f'Problem running collectstatic; output, ``{pprint.pformat(output)}``'
    return problem_message
