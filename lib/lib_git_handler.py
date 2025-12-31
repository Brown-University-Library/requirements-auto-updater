import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def run_git_status(project_path: Path) -> tuple[bool, dict]:
    """
    Runs `git status` and return the output similar to Go's (ok, err) format.
    Called by lib_environment_checker.check_git_status()
    """
    command = ['git', 'status']
    result: subprocess.CompletedProcess = subprocess.run(command, cwd=str(project_path), capture_output=True, text=True)
    log.debug(f'result: {result}')
    ok = True if result.returncode == 0 else False
    output = {'stdout': f'{result.stdout}', 'stderr': f'{result.stderr}'}
    return_val = (ok, output)
    log.debug(f'return_val: {return_val}')
    return return_val


class GitHandler:
    def __init__(self):
        pass

    def manage_git(self, project_path: Path, diff_text: str) -> None:
        """
        Manages the git process.
        Called by auto_updater.manage_update()
        """
        log.info('::: starting git process ----------')
        self.run_git_pull(project_path)
        self.run_git_add(project_path / 'uv.lock', project_path)
        self.run_git_commit(project_path, diff_text)
        self.run_git_push(project_path)
        return

    def run_git_pull(self, project_path: Path) -> tuple[bool, dict]:
        """
        Runs the git pull command.
        Called by manage_git()
        """
        log.info('::: running git pull ----------')
        git_pull_command: list[str] = ['git', 'pull', 'origin', 'main']
        result: subprocess.CompletedProcess = subprocess.run(
            git_pull_command, cwd=str(project_path), capture_output=True, text=True
        )
        log.debug(f'result: {result}')
        ok = True if result.returncode == 0 else False
        output = {'stdout': f'{result.stdout}', 'stderr': f'{result.stderr}'}
        log.debug(f'output: ``{output}``')
        if ok is True:
            log.info('ok / git pull successful')
        else:
            log.info('problem / git pull failed')
        return_val = (ok, output)
        return return_val

    def run_git_add(self, requirements_path: Path, project_path: Path) -> tuple[bool, dict]:
        """
        Runs `git add` and return the output.
        Called by manage_git()
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

    def run_git_commit(self, project_path: Path, diff_text: str) -> tuple[bool, dict]:
        """
        Runs the git commit command.
        Returns (success: bool, output: dict)
        Called by manage_git()
        """
        log.info('::: running git commit ----------')
        git_commit_command: list[str] = ['git', 'commit', '-am', 'auto-updater: update dependencies']
        result: subprocess.CompletedProcess = subprocess.run(
            git_commit_command, cwd=str(project_path), capture_output=True, text=True
        )
        log.debug(f'result: {result}')
        ok = True if result.returncode == 0 else False
        output = {'stdout': f'{result.stdout}', 'stderr': f'{result.stderr}'}

        if ok is True:
            log.info('ok / git commit successful')
        else:
            if 'nothing to commit' in result.stdout:
                log.info('ok / nothing to commit')
            else:
                log.warning(f'problem / git commit failed: {output}')

        return_val = (ok, output)
        log.debug(f'return_val: {return_val}')
        return return_val

    def run_git_push(self, project_path: Path) -> tuple[bool, dict]:
        """
        Runs the git push command.
        Returns (success: bool, output: dict)
        Called by manage_git()
        """
        log.info('::: running git push ----------')
        git_push_command: list[str] = ['git', 'push']
        result: subprocess.CompletedProcess = subprocess.run(
            git_push_command, cwd=str(project_path), capture_output=True, text=True
        )
        log.debug(f'result: {result}')
        ok = True if result.returncode == 0 else False
        output = {'stdout': f'{result.stdout}', 'stderr': f'{result.stderr}'}

        if ok is True:
            log.info('ok / git push successful')
        else:
            log.warning(f'problem / git push failed: {output}')

        return_val = (ok, output)
        log.debug(f'return_val: {return_val}')
        return return_val

    ## end class GitHandler
