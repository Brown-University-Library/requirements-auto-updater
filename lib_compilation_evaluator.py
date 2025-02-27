"""
Module used by self_updater.py
Contains code for comparing the newly-compiled `requirements.txt` with the most recent one.
"""

import difflib
import logging
from pathlib import Path

import lib_git_handler

log = logging.getLogger(__name__)


class CompiledComparator:
    def __init__(self):
        pass

    # def compare_with_previous_backup(
    #     self, new_path: Path, old_path: Path | None = None, project_path: Path | None = None
    # ) -> bool:
    #     """
    #     Compares the newly created `requirements.txt` with the most recent one.
    #     Ignores initial lines starting with '#' in the comparison.
    #     Returns False if there are no changes, True otherwise.
    #     (Currently the manager-script just passes in the new_path, and the old_path is determined.)
    #     """
    #     log.info('::: starting compare to check for changes ----------')
    #     changes = True
    #     ## try to get the old-path --------------------------------------
    #     if not old_path:
    #         log.debug('old_path not passed in; looking for it in `requirements_backups`')
    #         backup_dir: Path = project_path.parent / 'requirements_backups'
    #         log.debug(f'backup_dir: ``{backup_dir}``')
    #         backup_files: list[Path] = sorted([f for f in backup_dir.iterdir() if f.suffix == '.txt'], reverse=True)
    #         old_path: Path | None = backup_files[1] if len(backup_files) > 1 else None
    #         log.debug(f'old_file: ``{old_path}``')
    #     if not old_path:
    #         log.debug('no previous backups found, so changes=False.')
    #         changes = False
    #     else:
    #         ## compare the two files ------------------------------------
    #         with new_path.open() as curr, old_path.open() as prev:
    #             curr_lines = curr.readlines()
    #             prev_lines = prev.readlines()
    #             curr_lines_filtered = self.filter_initial_comments(curr_lines)  # removes initial comments
    #             prev_lines_filtered = self.filter_initial_comments(prev_lines)  # removes initial comments
    #             if curr_lines_filtered == prev_lines_filtered:
    #                 log.debug('no differences found in dependencies.')
    #                 changes = False
    #     log.info(f'ok / changes, ``{changes}``')
    #     return changes  # just the boolean

    def compare_with_previous_backup(
        self, new_path: Path, old_path: Path | None = None, project_path: Path | None = None
    ) -> bool:
        """
        Compares the newly created `requirements.txt` with the most recent one.
        Ignores initial lines starting with '#' in the comparison.
        Returns False if there are no changes, True otherwise.
        (Currently the manager-script just passes in the new_path, and the old_path is determined.)
        """
        log.info('::: starting compare to check for changes ----------')
        changes = True
        ## try to get the old-path --------------------------------------
        if not old_path:
            if project_path is None:
                msg = 'project_path must be passed in if old_path is not passed in.'
                log.exception(msg)
                raise Exception(msg)
            log.debug('old_path not passed in; looking for it in `requirements_backups`')
            backup_dir: Path = project_path.parent / 'requirements_backups'
            log.debug(f'backup_dir: ``{backup_dir}``')
            backup_files: list[Path] = sorted([f for f in backup_dir.iterdir() if f.suffix == '.txt'], reverse=True)
            # old_path: Path | None = backup_files[1] if len(backup_files) > 1 else None
            # log.debug(f'old_file: ``{old_path}``')
            determined_old_path: Path | None = backup_files[1] if len(backup_files) > 1 else None
            log.debug(f'determined_old_path: ``{determined_old_path}``')
            old_path = determined_old_path
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
        log.info(f'ok / changes, ``{changes}``')
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
        log.info('::: making diff-text ----------')
        ## get the two most recent backup files ---------------------
        backup_dir: Path = project_path.parent / 'requirements_backups'
        log.debug(f'backup_dir: ``{backup_dir}``')
        backup_files: list[Path] = sorted([f for f in backup_dir.iterdir() if f.suffix == '.txt'], reverse=True)
        current_file: Path = backup_files[0]
        log.debug(f'current_file: ``{current_file}``')
        previous_file: Path | None = backup_files[1] if len(backup_files) > 1 else None
        log.debug(f'previous_file: ``{previous_file}``')
        ## create the diff-text -------------------------------------
        if not previous_file:
            log.debug('no previous backups found, so returning empty string.')
            diff_text = ''
        else:
            with current_file.open() as curr, previous_file.open() as prev:
                ## prepare the lines for the diff -------------------
                curr_lines = curr.readlines()
                prev_lines = prev.readlines()
                curr_lines_filtered = self.filter_initial_comments(curr_lines)  # removes initial comments
                prev_lines_filtered = self.filter_initial_comments(prev_lines)  # removes initial comments
                ## build the diff info ------------------------------
                diff_lines = [f'--- {previous_file.name}\n', f'+++ {current_file.name}\n']
                diff_lines.extend(difflib.unified_diff(prev_lines_filtered, curr_lines_filtered))
                diff_text = ''.join(diff_lines)
        log.info(f'ok / diff_text, ``{diff_text}``')
        return diff_text

    def copy_new_compile_to_codebase(self, compiled_requirements: Path, project_path: Path, environment_type: str) -> str:
        """
        Copies the newly compiled requirements file to the project's codebase.
        Then commits and pushes the changes to the project's git repository.

        Note: reads and writes the requirements `.txt` file to avoid explicit full-path references.

        Called by self_updater.py.
        """
        log.info('::: copying new compile to codebase ----------')
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
            log.info('ok / new requirements file copied to project.')
        except Exception as e:
            problem_message = f'Error copying new requirements file to project; error: ``{e}``'
            log.exception(problem_message)

        ## run git-pull ---------------------------------------------
        """
        Handles situation where ok=True, and stdout includes 'Already up to date', and stderr contains tag info.
        """
        call_result: tuple[bool, dict] = lib_git_handler.run_git_pull(project_path)
        (ok, output) = call_result
        if not ok:
            if output['stderr']:
                problem_message += f'\nError with git-pull; stderr: ``{output["stderr"]}``'
                log.error(f'problem_message now, ``{problem_message}``')

        ## run git-add ----------------------------------------------
        call_result: tuple[bool, dict] = lib_git_handler.run_git_add(save_path, project_path)
        (ok, output) = call_result
        if output['stderr']:
            problem_message += f'\nError with git-add; stderr: ``{output["stderr"]}``'
            log.error(f'problem_message now, ``{problem_message}``')

        ## run a git-commit via subprocess --------------------------
        """
        Handles `nothing to commit, working tree clean` situation, where ok=False, stderr is '', and stdout contains that message.
        """
        call_result: tuple[bool, dict] = lib_git_handler.run_git_commit(project_path)
        (ok, output) = call_result
        if output['stderr']:
            problem_message += f'\nError with git-commit; stderr: ``{output["stderr"]}``'
            log.error(f'problem_message now, ``{problem_message}``')

        ## run a git-push via subprocess ----------------------------
        """
        Handles `Everything up-to-date` situation, where ok=True, stdout is '', and stderr contains that message.
        """
        call_result: tuple[bool, dict] = lib_git_handler.run_git_push(project_path)
        (ok, output) = call_result
        if not ok:
            if output['stderr']:
                problem_message += f'\nError with git-push; stderr: ``{output["stderr"]}``'
                log.error(f'problem_message now, ``{problem_message}``')

        log.debug(f'final problem_message: ``{problem_message}``')
        return problem_message

        ## end def copy_new_compile_to_codebase()

    ## end class CompiledComparator
