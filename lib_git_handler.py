import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def run_git_status(project_path: Path) -> tuple[bool, dict]:
    """
    Runs `git status` and return the output similar to Go's (ok, err) format.
    """
    command = ['git', 'status']
    result: subprocess.CompletedProcess = subprocess.run(command, cwd=str(project_path), capture_output=True, text=True)
    log.debug(f'result: {result}')
    ok = True if result.returncode == 0 else False
    output = {'stdout': f'{result.stdout}', 'stderr': f'{result.stderr}'}
    return_val = (ok, output)
    log.debug(f'return_val: {return_val}')
    return return_val


def run_git_pull(project_path: Path) -> tuple[bool, dict]:
    """
    Runs `git pull` and return the output.
    Possible TODO: pass in the dir-path as an argument.
    Note to self: subprocess.run's `cwd` param changes the current-working-directory before the command is run,
      and leaves it there.
    """
    log.info('::: running git pull ----------')
    command = ['git', 'pull']
    result: subprocess.CompletedProcess = subprocess.run(command, cwd=str(project_path), capture_output=True, text=True)
    log.debug(f'result: {result}')
    ok = True if result.returncode == 0 else False
    if ok is True:
        log.info('ok / git pull successful')
    output = {'stdout': f'{result.stdout}', 'stderr': f'{result.stderr}'}
    return_val = (ok, output)
    log.debug(f'return_val: {return_val}')
    return return_val


def run_git_add(requirements_path: Path, project_path: Path) -> tuple[bool, dict]:
    """
    Runs `git add` and return the output.
    """
    log.info('::: running git add ----------')
    command = ['git', 'add', str(requirements_path)]
    result: subprocess.CompletedProcess = subprocess.run(command, cwd=str(project_path), capture_output=True, text=True)
    log.debug(f'result: {result}')
    ok = True if result.returncode == 0 else False
    if ok is True:
        log.info('ok / git add successful')
    output = {'stdout': f'{result.stdout}', 'stderr': f'{result.stderr}'}
    return_val = (ok, output)
    log.debug(f'return_val: {return_val}')
    return return_val
