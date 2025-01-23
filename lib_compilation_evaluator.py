"""
Module used by self_updater.py
Contains code for comparing the newly-compiled `requirements.txt` with the most recent one.
"""

import difflib
import logging
import subprocess
from pathlib import Path

from self_updater_code import lib_git_handler

log = logging.getLogger(__name__)


class CompiledComparator:
    def __init__(self):
        pass

    def compare_with_previous_backup(
        self, new_path: Path, old_path: Path | None = None, project_path: Path | None = None
    ) -> bool:
        """
        Compares the newly created `requirements.txt` with the most recent one.
        Ignores initial lines starting with '#' in the comparison.
        Returns False if there are no changes, True otherwise.
        (Currently the manager-script just passes in the new_path, and the old_path is determined.)
        """
        log.debug('starting compare_with_previous_backup()')
        changes = True
        ## try to get the old-path --------------------------------------
        if not old_path:
            log.debug('old_path not passed in; looking for it in `requirements_backups`')
            backup_dir: Path = project_path.parent / 'requirements_backups'
            log.debug(f'backup_dir: ``{backup_dir}``')
            backup_files: list[Path] = sorted([f for f in backup_dir.iterdir() if f.suffix == '.txt'], reverse=True)
            old_path: Path | None = backup_files[1] if len(backup_files) > 1 else None
            log.debug(f'old_file: ``{old_path}``')
        if not old_path:
            log.debug('no previous backups found, so changes=False.')
            changes = False
        else:
            ## compare the two files ------------------------------------
            with new_path.open() as curr, old_path.open() as prev:
                curr_lines = curr.readlines()
                prev_lines = prev.readlines()
                curr_lines_filtered = self.filter_initial_comments(curr_lines)  # removes initial comments
                prev_lines_filtered = self.filter_initial_comments(prev_lines)  # removes initial comments
                if curr_lines_filtered == prev_lines_filtered:
                    log.debug('no differences found in dependencies.')
                    changes = False
        log.debug(f'changes: ``{changes}``')
        return changes  # just the boolean

    def filter_initial_comments(self, lines: list[str]) -> list[str]:
        """
        Filters out initial lines starting with '#' from a list of lines.
        The reason for this is that:
        - one of the first line of the backup file includes a timestamp, which would always be different.
        - if a generated `.txt` file is used to update the venv, the string `# ACTIVE`
            is added to the top of the file, which would always be different from a fresh compile.
        Called by `compare_with_previous_backup()`.
        """
        log.debug('starting filter_initial_comments()')
        non_comment_index = next((i for i, line in enumerate(lines) if not line.startswith('#')), len(lines))
        return lines[non_comment_index:]

    def make_diff_text(self, project_path: Path) -> str:
        """
        Creates a diff from the two most recent requirements files.
        Called by send_email_of_diffs().
        """
        log.debug('starting make_diff_text()')
        ## get the two most recent backup files -------------------------
        backup_dir: Path = project_path.parent / 'requirements_backups'
        log.debug(f'backup_dir: ``{backup_dir}``')
        backup_files: list[Path] = sorted([f for f in backup_dir.iterdir() if f.suffix == '.txt'], reverse=True)
        current_file: Path = backup_files[0]
        log.debug(f'current_file: ``{current_file}``')
        previous_file: Path | None = backup_files[1] if len(backup_files) > 1 else None
        log.debug(f'previous_file: ``{previous_file}``')

        with current_file.open() as curr, previous_file.open() as prev:
            ## prepare the lines for the diff ---------------------------
            curr_lines = curr.readlines()
            prev_lines = prev.readlines()
            curr_lines_filtered = self.filter_initial_comments(curr_lines)  # removes initial comments
            prev_lines_filtered = self.filter_initial_comments(prev_lines)  # removes initial comments
            ## build the diff info --------------------------------------
            diff_lines = [f'--- {previous_file.name}\n', f'+++ {current_file.name}\n']
            diff_lines.extend(difflib.unified_diff(prev_lines_filtered, curr_lines_filtered))
            diff_text = ''.join(diff_lines)
        log.debug(f'diff_text: ``{diff_text}``')
        return diff_text

    def copy_new_compile_to_codebase(self, compiled_requirements: Path, project_path: Path, environment_type: str) -> str:
        """
        Copies the newly compiled requirements file to the project's codebase.
        Then commits and pushes the changes to the project's git repository.

        Note: reads and writes the requirements `.txt` file to avoid explicit full-path references.

        Called by self_updater.py.
        """
        log.debug('starting copy_new_compile_to_codebase()')
        ## copy new requirements file to project --------------------
        problem_message = ''
        try:
            assert environment_type in ['local', 'staging', 'production']
            ## make save-path ---------------------------------------
            save_path: Path = project_path / 'requirements' / f'{environment_type}.txt'
            ## copy the new requirements file to the project --------
            compiled_requirements_lines = compiled_requirements.read_text().splitlines()
            compiled_requirements_lines = [line for line in compiled_requirements_lines if not line.startswith('#')]
            save_path.write_text('\n'.join(compiled_requirements_lines))
            log.debug('new requirements file copied to project.')
        except Exception as e:
            problem_message = f'Error copying new requirements file to project; error: ``{e}``'
            log.exception(problem_message)
        ## run git-pull ---------------------------------------------
        lib_git_handler.run_git_pull(project_path)
        ## run git-add ----------------------------------------------
        lib_git_handler.run_git_add(save_path, project_path)
        try:
            ## run a git-commit via subprocess ------------------------
            command = ['git', 'commit', '-m', 'auto-update of requirements']
            log.debug(f'git-commit-command, ``{command}``')
            subprocess.run(command, cwd=project_path, check=True, capture_output=True, text=True)
            ## run a git-push via subprocess ------------------------
            command = ['git', 'push', 'origin', 'main']
            log.debug(f'git-push command, ``{command}``')
            subprocess.run(command, cwd=project_path, check=True)
        except Exception as e:
            log.debug(f'e.returncode, ``{e.returncode}``')
            stderr_output = e.stderr or ''  # safeguard against None
            log.debug(f'stderr_output, ``{stderr_output}``')
            if e.returncode == 1 and 'nothing to commit' in stderr_output.lower():
                log.debug('no real commit error')
            else:
                git_problem_message = f'Error with git-pull or git-commit or git-push; error: ``{e}``'
            log.debug(f'git_problem_message: ``{git_problem_message}``')
            log.exception(git_problem_message)
            if problem_message:
                problem_message += f' Also: {git_problem_message}'
        log.debug(f'problem_message: ``{problem_message}``')
        return problem_message

        ## end def copy_new_compile_to_codebase()

    # def copy_new_compile_to_codebase(self, compiled_requirements: Path, project_path: Path, environment_type: str) -> str:
    #     """
    #     Copies the newly compiled requirements file to the project's codebase.
    #     Then commits and pushes the changes to the project's git repository.

    #     Note: reads and writes the requirements `.txt` file to avoid explicit full-path references.

    #     Called by self_updater.py.
    #     """
    #     log.debug('starting copy_new_compile_to_codebase()')
    #     problem_message = ''
    #     try:
    #         assert environment_type in ['local', 'staging', 'production']
    #         ## make save-path -------------------------------------------
    #         save_path: Path = project_path / 'requirements' / f'{environment_type}.txt'
    #         ## copy the new requirements file to the project --------------
    #         compiled_requirements_lines = compiled_requirements.read_text().splitlines()
    #         compiled_requirements_lines = [line for line in compiled_requirements_lines if not line.startswith('#')]
    #         save_path.write_text('\n'.join(compiled_requirements_lines))
    #         log.debug('new requirements file copied to project.')
    #     except Exception as e:
    #         problem_message = f'Error copying new requirements file to project; error: ``{e}``'
    #         log.exception(problem_message)
    #     try:
    #         ## run a git-pull via subprocess ------------------------
    #         command = ['git', 'pull']
    #         log.debug(f'git-pull-command, ``{command}``')
    #         subprocess.run(command, cwd=project_path, check=True)
    #         ## run a git-add via subprocess -------------------------
    #         command = ['git', 'add', str(save_path)]
    #         log.debug(f'git-add-command, ``{command}``')
    #         subprocess.run(command, cwd=project_path, check=True)
    #         ## run a git-commit via subprocess ------------------------
    #         command = ['git', 'commit', '-m', 'auto-update of requirements']
    #         log.debug(f'git-commit-command, ``{command}``')
    #         subprocess.run(command, cwd=project_path, check=True)
    #         ## run a git-push via subprocess ------------------------
    #         command = ['git', 'push', 'origin', 'main']
    #         log.debug(f'git-push command, ``{command}``')
    #         subprocess.run(command, cwd=project_path, check=True)
    #     except Exception as e:
    #         git_problem_message = f'Error with git-pull or git-commit or git-push; error: ``{e}``'
    #         log.debug(f'git_problem_message: ``{git_problem_message}``')
    #         log.exception(git_problem_message)
    #         if problem_message:
    #             problem_message += f' Also: {git_problem_message}'
    #     log.debug(f'problem_message: ``{problem_message}``')
    #     return problem_message

    #     ## end def copy_new_compile_to_codebase()

    ## end class CompiledComparator
