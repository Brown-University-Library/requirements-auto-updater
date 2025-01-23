import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def run_git_pull() -> tuple[bool, dict]:
    """
    (not yet used by code -- just by a test)

    Runs `git pull` and return the output similar to Go's (ok, err) format.
    Possible TODO: pass in the dir-path as an argument.
    Note to self: subprocess.run's `cwd` param changes the current-working-directory before the command is run,
      and leaves it there.
    """
    cur_dir = Path('./').resolve()
    log.debug(f'cur_dir: {cur_dir}')
    command = ['git', 'pull']
    result: subprocess.CompletedProcess = subprocess.run(command, cwd=cur_dir, capture_output=True, text=True)
    log.debug(f'result: {result}')
    ok = True if result.returncode == 0 else False
    output = {'stdout': f'{result.stdout}', 'stderr': f'{result.stderr}'}
    return_val = (ok, output)
    log.debug(f'return_val: {return_val}')
    return return_val
