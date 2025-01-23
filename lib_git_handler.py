import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def run_git_pull() -> str:
    """
    Run `git pull` and return the output.
    """
    cur_dir = Path('./').resolve()
    log.debug(f'cur_dir: {cur_dir}')
    command = ['git', 'pull']
    # result = subprocess.run(command, cwd=cur_dir, check=True, capture_output=True, text=True)
    result = subprocess.run(command, cwd=cur_dir, capture_output=True, text=True)
    log.debug(f'type(result): {type(result)}')
    log.debug(f'result: {result}')
    return result
