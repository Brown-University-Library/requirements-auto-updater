import logging
import os
import subprocess

log = logging.getLogger(__name__)


def check_for_django_update(incoming_text: str) -> bool:
    """
    Checks if incoming diff-text indicates a django update.

    Iterates through lines of incoming text.
    - first strips whitespace from each line
    - then checks if the string '+django==' is in the line
    """
    return_val: bool = False
    incoming_lines: list = incoming_text.split('\n')
    for line in incoming_lines:
        line: str = line.strip()
        if '+django==' in line:
            return_val = True
            break
    log.debug(f'return_val: {return_val}')
    return return_val


def run_collectstatic() -> None | str:
    """
    Runs collectstatic command.
    """
    try:
        ## log cwd
        log.debug(f'cwd: {os.getcwd()}')
        command = ['bash', '-c', 'source ..env/bin/activate && python ./manage.py collectstatic --noinput']
        log.debug(f'command: {command}')
        subprocess.run(command, check=True)
        message = None
    except subprocess.CalledProcessError as e:
        message = f'Error running collectstatic: {e}'
        log.exception(message)
    log.debug(f'message: {message}')
    return message
