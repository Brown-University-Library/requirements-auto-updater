import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def run_git_pull(project_path: Path) -> tuple[bool, dict]:
    """
    Runs `git pull` and return the output similar to Go's (ok, err) format.
    Possible TODO: pass in the dir-path as an argument.
    Note to self: subprocess.run's `cwd` param changes the current-working-directory before the command is run,
      and leaves it there.
    """
    command = ['git', 'pull']
    result: subprocess.CompletedProcess = subprocess.run(command, cwd=str(project_path), capture_output=True, text=True)
    log.debug(f'result: {result}')
    ok = True if result.returncode == 0 else False
    output = {'stdout': f'{result.stdout}', 'stderr': f'{result.stderr}'}
    return_val = (ok, output)
    log.debug(f'return_val: {return_val}')
    return return_val


def run_git_add(requirements_path: Path, project_path: Path) -> tuple[bool, dict]:
    """
    Runs `git add` and return the output.
    """
    command = ['git', 'add', str(requirements_path)]
    result: subprocess.CompletedProcess = subprocess.run(command, cwd=str(project_path), capture_output=True, text=True)
    log.debug(f'result: {result}')
    ok = True if result.returncode == 0 else False
    output = {'stdout': f'{result.stdout}', 'stderr': f'{result.stderr}'}
    return_val = (ok, output)
    log.debug(f'return_val: {return_val}')
    return return_val