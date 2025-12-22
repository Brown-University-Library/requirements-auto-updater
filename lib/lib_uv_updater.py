"""
Module used by auto_updater.py
Contains code for comparing the newly-compiled `requirements.txt` with the most recent one.
"""

import datetime
import difflib
import logging
import pprint
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


class UvUpdater:
    def __init__(self):
        pass

    def manage_sync(self, uv_path: Path, project_path: Path, environment_type: str) -> None:
        """
        Manages the sync process.
        """
        log.info('::: starting uv sync ----------')
        self.backup_uv_lock(uv_path, project_path)
        sync_type = '--upgrade'
        sync_command: list[str] = self.make_sync_command(uv_path, environment_type, sync_type)
        output: tuple[bool, dict] = self.run_standard_sync_command(sync_command, project_path)
        ok, std_dct = output
        if ok is True:
            pass
        else:  ## revert / TODO: do these in steps, building good problem message for email
            problem_message = 'problem / uv sync failed'
            ## copy the backup back to uv.lock
            shutil.copy(project_path.parent / 'uv.lock.bak', project_path / 'uv.lock')
            ## run `uv sync --frozen` to revert the .venv
            sync_command: list[str] = self.make_sync_command(uv_path, environment_type, '--frozen')
            error_str: str = self.run_frozen_sync_command(sync_command, project_path)
            if error_str:
                problem_message = '\n\n' + error_str
            ## check run_tests again
            run_tests_command: list[str] = self.make_run_tests_command(uv_path, environment_type)
            error_str: str = self.run_run_tests_command(run_tests_command, project_path)
            if error_str:
                problem_message = '\n\n' + error_str
            ## email admins with all errors
            # email_admins_with_errors(problem_message)  # TODO
        return

    def backup_uv_lock(self, uv_path: Path, project_path: Path) -> Path:
        """
        Backs up the uv.lock file.
        """
        import shutil

        assert isinstance(uv_path, Path), f'type(uv_path) is {type(uv_path)}'
        uv_lock_path: Path = project_path / 'uv.lock'
        backup_file_path: Path = project_path.parent / 'uv.lock.bak'
        shutil.copy(uv_lock_path, backup_file_path)
        assert backup_file_path.exists(), f'backup_file_path does not exist, ``{backup_file_path}``'
        return backup_file_path

    # def make_sync_command(self, uv_path: Path, environment_type: str, sync_type: str) -> list[str]:
    #     """
    #     Makes the sync command.
    #     """
    #     if environment_type == 'local':
    #         group = 'local'
    #     elif environment_type == 'staging':
    #         group = 'staging'
    #     elif environment_type == 'production':
    #         group = 'production'
    #     else:
    #         msg = f'Invalid environment_type: {environment_type}'
    #         log.exception(msg)
    #         raise Exception(msg)
    #     cmnd: list[str] = [str(uv_path), 'sync', sync_type, '--group', group]
    #     log.debug(f'cmnd, ``{cmnd}``')
    #     return cmnd

    def make_sync_command(self, uv_path: Path, environment_type: str, sync_type: str) -> list[str]:
        """
        Makes the sync command.
        """
        if environment_type == 'local':
            group = 'local'
        elif environment_type == 'staging':
            group = 'staging'
        elif environment_type == 'production':
            group = 'production'
        else:
            msg = f'Invalid environment_type: {environment_type}'
            log.exception(msg)
            raise Exception(msg)
        iso_date: str = self.make_iso_date()  # the iso-date for a week ago
        cmnd: list[str] = [str(uv_path), 'sync', sync_type, '--group', group, '--exclude-newer', iso_date]
        log.debug(f'cmnd, ``{cmnd}``')
        return cmnd

    def make_iso_date(self) -> str:
        """
        Makes an ISO date for a week ago.
        Called by make_sync_command()
        """
        iso_date: str = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
        log.debug(f'iso_date, ``{iso_date}``')
        return iso_date

    def run_standard_sync_command(self, sync_command: list[str], project_path: Path) -> tuple[bool, dict]:
        """
        Runs the initial --upgrade sync command.
        """
        result: subprocess.CompletedProcess = subprocess.run(
            sync_command, cwd=str(project_path), capture_output=True, text=True
        )
        log.debug(f'result: {result}')
        ok = True if result.returncode == 0 else False
        if ok is True:
            log.info('ok / uv sync successful')
        else:
            log.info('problem / uv sync failed')
        output = {'stdout': f'{result.stdout}', 'stderr': f'{result.stderr}'}
        return_val = (ok, output)
        log.debug(f'return_val: {return_val}')
        return return_val

    def run_frozen_sync_command(self, sync_command: list[str], project_path: Path) -> str:
        """
        Runs the frozen sync command.
        """
        error_str: str = ''
        result: subprocess.CompletedProcess = subprocess.run(
            sync_command, cwd=str(project_path), capture_output=True, text=True
        )
        log.debug(f'result: {result}')
        ok = True if result.returncode == 0 else False
        if ok is True:
            log.debug('restored frozen uv sync successful')
            error_str = ''
        else:
            error_output = {'stdout': f'{result.stdout}', 'stderr': f'{result.stderr}'}
            log.debug(f'error_output, ``{pprint.pformat(error_output)}``')
            error_str = 'problem: restoring previous uv sync failed; see log output.'
        return error_str

    def compare_uv_lock_files(self, uv_lock_path: Path, uv_lock_backup_path: Path) -> dict[str, str | bool]:
        """
        Compares the current `uv.lock` file with its backup and returns a structured result.

        Returns a dictionary with keys:
        - "changes": bool — True if files differ; False otherwise (or on error)
        - "diff": str — unified diff text if differences exist; empty string otherwise
        """
        log.info('::: comparing uv.lock files ----------')
        try:
            with uv_lock_path.open() as curr, uv_lock_backup_path.open() as prev:
                ## read lines ---------------------------------------
                curr_lines = [line.rstrip() for line in curr.readlines()]
                prev_lines = [line.rstrip() for line in prev.readlines()]
                ## generate unified diff ----------------------------
                diff: list[str] = list(
                    difflib.unified_diff(
                        prev_lines, curr_lines, fromfile=str(uv_lock_backup_path), tofile=str(uv_lock_path), lineterm=''
                    )
                )
                log.debug(f'diff: \n{pprint.pformat(diff)}')
                ## log the diff if there are differences ------------
                if diff:
                    log.info('ok / differences found between uv.lock and its backup')
                else:
                    log.info('ok / no differences found between uv.lock and its backup')
            diff_text: str = '\n'.join(diff) + '\n'
            log.debug(f'diff_text: \n{diff_text}')
            changes: bool = bool(diff)
            return {"changes": changes, "diff": diff_text}
        except Exception as e:
            log.error(f'Error comparing uv.lock files: {str(e)}')
            # TODO: email admins
            return {"changes": False, "diff": ""}

    # def compare_uv_lock_files(self, uv_lock_path: Path, uv_lock_backup_path: Path) -> str | None:
    #     """
    #     Compares the uv.lock file with the backup and returns True if they differ.
    #     Uses Python's difflib to generate a unified diff.
    #     """
    #     log.info('::: comparing uv.lock files ----------')
    #     try:
    #         with uv_lock_path.open() as curr, uv_lock_backup_path.open() as prev:
    #             ## read lines ---------------------------------------
    #             curr_lines = [line.rstrip() for line in curr.readlines()]
    #             prev_lines = [line.rstrip() for line in prev.readlines()]
    #             ## generate unified diff ----------------------------
    #             diff: list[str] = list(
    #                 difflib.unified_diff(
    #                     prev_lines, curr_lines, fromfile=str(uv_lock_backup_path), tofile=str(uv_lock_path), lineterm=''
    #                 )
    #             )
    #             log.debug(f'diff: \n{pprint.pformat(diff)}')
    #             ## log the diff if there are differences ------------
    #             if diff:
    #                 log.info('ok / differences found between uv.lock and its backup')
    #             else:
    #                 log.info('ok / no differences found between uv.lock and its backup')
    #         diff_text: str = '\n'.join(diff) + '\n'
    #         log.debug(f'diff_text: \n{diff_text}')
    #         return diff_text
    #     except Exception as e:
    #         log.error(f'Error comparing uv.lock files: {str(e)}')
    #         # TODO: email admins
    #         return None


## end class UvUpdater


# class GitHandler:
#     def __init__(self):
#         pass

#     def manage_git(self, project_path: Path, diff_text: str) -> None:
#         """
#         Manages the git process.
#         """
#         log.info('::: starting git process ----------')
#         self.run_git_pull(project_path)
#         self.run_git_add(project_path / 'requirements.txt', project_path)
#         self.run_git_commit(project_path, diff_text)
#         self.run_git_push(project_path)
#         return

#     def run_git_pull(self, project_path: Path) -> None:
#         """
#         Runs the git pull command.
#         """
#         log.info('::: running git pull ----------')
#         git_pull_command: list[str] = ['git', 'pull']
#         result: subprocess.CompletedProcess = subprocess.run(git_pull_command, cwd=str(project_path))
#         log.debug(f'result: {result}')
#         ok = True if result.returncode == 0 else False
#         if ok is True:
#             log.info('ok / git pull successful')
#         else:
#             log.info('problem / git pull failed')
#         return

#     def run_git_add(self, requirements_path: Path, project_path: Path) -> tuple[bool, dict]:
#         """
#         Runs `git add` and return the output.
#         """
#         log.info('::: running git add ----------')
#         command = ['git', 'add', str(requirements_path)]
#         result: subprocess.CompletedProcess = subprocess.run(command, cwd=str(project_path), capture_output=True, text=True)
#         log.debug(f'result: {result}')
#         ok = True if result.returncode == 0 else False
#         if ok is True:
#             log.info('ok / git add successful')
#         output = {'stdout': f'{result.stdout}', 'stderr': f'{result.stderr}'}
#         return_val = (ok, output)
#         log.debug(f'return_val: {return_val}')
#         return return_val

#     def run_git_commit(self, project_path: Path, diff_text: str) -> None:
#         """
#         Runs the git commit command.
#         """
#         log.info('::: running git commit ----------')
#         git_commit_command: list[str] = ['git', 'commit', '-am', 'auto-updater: update dependencies']
#         result: subprocess.CompletedProcess = subprocess.run(git_commit_command, cwd=str(project_path))
#         log.debug(f'result: {result}')
#         ok = True if result.returncode == 0 else False
#         if ok is True:
#             log.info('ok / git commit successful')
#         else:
#             log.info('problem / git commit failed')
#         return

#     def run_git_push(self, project_path: Path) -> None:
#         """
#         Runs the git push command.
#         """
#         log.info('::: running git push ----------')
#         git_push_command: list[str] = ['git', 'push']
#         result: subprocess.CompletedProcess = subprocess.run(git_push_command, cwd=str(project_path))
#         log.debug(f'result: {result}')
#         ok = True if result.returncode == 0 else False
#         if ok is True:
#             log.info('ok / git push successful')
#         else:
#             log.info('problem / git push failed')
#         return

#     ## end class GitHandler


# class CompiledComparator:
#     def __init__(self):
#         pass

#     def compare_with_previous_backup(
#         self, new_path: Path, old_path: Path | None = None, project_path: Path | None = None
#     ) -> bool:
#         """
#         Compares the newly created `requirements.txt` with the most recent one.
#         Ignores initial lines starting with '#' in the comparison.
#         Returns False if there are no changes, True otherwise.
#         (Currently the manager-script just passes in the new_path, and the old_path is determined.)
#         """
#         log.info('::: starting compare to check for changes ----------')
#         changes = True
#         ## try to get the old-path --------------------------------------
#         if not old_path:
#             if project_path is None:
#                 msg = 'project_path must be passed in if old_path is not passed in.'
#                 log.exception(msg)
#                 raise Exception(msg)
#             log.debug('old_path not passed in; looking for it in `requirements_backups`')
#             backup_dir: Path = project_path.parent / 'requirements_backups'
#             log.debug(f'backup_dir: ``{backup_dir}``')
#             backup_files: list[Path] = sorted([f for f in backup_dir.iterdir() if f.suffix == '.txt'], reverse=True)
#             # old_path: Path | None = backup_files[1] if len(backup_files) > 1 else None
#             # log.debug(f'old_file: ``{old_path}``')
#             determined_old_path: Path | None = backup_files[1] if len(backup_files) > 1 else None
#             log.debug(f'determined_old_path: ``{determined_old_path}``')
#             old_path = determined_old_path
#         if not old_path:
#             log.debug('no previous backups found, so changes=False.')
#             changes = False
#         else:
#             ## compare the two files ------------------------------------
#             with new_path.open() as curr, old_path.open() as prev:
#                 curr_lines = curr.readlines()
#                 prev_lines = prev.readlines()
#                 curr_lines_filtered = self.filter_initial_comments(curr_lines)  # removes initial comments
#                 prev_lines_filtered = self.filter_initial_comments(prev_lines)  # removes initial comments
#                 if curr_lines_filtered == prev_lines_filtered:
#                     log.debug('no differences found in dependencies.')
#                     changes = False
#         log.info(f'ok / changes, ``{changes}``')
#         return changes  # just the boolean

#     def filter_initial_comments(self, lines: list[str]) -> list[str]:
#         """
#         Filters out initial lines starting with '#' from a list of lines.
#         The reason for this is that:
#         - one of the first line of the backup file includes a timestamp, which would always be different.
#         - if a generated `.txt` file is used to update the venv, the string `# ACTIVE`
#             is added to the top of the file, which would always be different from a fresh compile.
#         Called by `compare_with_previous_backup()`.
#         """
#         log.debug('starting filter_initial_comments()')
#         non_comment_index = next((i for i, line in enumerate(lines) if not line.startswith('#')), len(lines))
#         return lines[non_comment_index:]

#     def make_diff_text(self, project_path: Path) -> str:
#         """
#         Creates a diff from the two most recent requirements files.
#         Called by send_email_of_diffs().
#         """
#         log.info('::: making diff-text ----------')
#         ## get the two most recent backup files ---------------------
#         backup_dir: Path = project_path.parent / 'requirements_backups'
#         log.debug(f'backup_dir: ``{backup_dir}``')
#         backup_files: list[Path] = sorted([f for f in backup_dir.iterdir() if f.suffix == '.txt'], reverse=True)
#         current_file: Path = backup_files[0]
#         log.debug(f'current_file: ``{current_file}``')
#         previous_file: Path | None = backup_files[1] if len(backup_files) > 1 else None
#         log.debug(f'previous_file: ``{previous_file}``')
#         ## create the diff-text -------------------------------------
#         if not previous_file:
#             log.debug('no previous backups found, so returning empty string.')
#             diff_text = ''
#         else:
#             with current_file.open() as curr, previous_file.open() as prev:
#                 ## prepare the lines for the diff -------------------
#                 curr_lines = curr.readlines()
#                 prev_lines = prev.readlines()
#                 curr_lines_filtered = self.filter_initial_comments(curr_lines)  # removes initial comments
#                 prev_lines_filtered = self.filter_initial_comments(prev_lines)  # removes initial comments
#                 ## build the diff info ------------------------------
#                 diff_lines = [f'--- {previous_file.name}\n', f'+++ {current_file.name}\n']
#                 diff_lines.extend(difflib.unified_diff(prev_lines_filtered, curr_lines_filtered))
#                 diff_text = ''.join(diff_lines)
#         log.info(f'ok / diff_text, ``{diff_text}``')
#         return diff_text

#     def copy_new_compile_to_codebase(self, compiled_requirements: Path, project_path: Path, environment_type: str) -> str:
#         """
#         Copies the newly compiled requirements file to the project's codebase.
#         Then commits and pushes the changes to the project's git repository.

#         Note: reads and writes the requirements `.txt` file to avoid explicit full-path references.

#         Called by auto_updater.py.
#         """
#         log.info('::: copying new compile to codebase ----------')
#         ## copy new requirements file to project --------------------
#         problem_message = ''
#         try:
#             assert environment_type in ['local', 'staging', 'production']
#             ## make save-path ---------------------------------------
#             save_path: Path = project_path / 'requirements' / f'{environment_type}.txt'
#             ## copy the new requirements file to the project --------
#             compiled_requirements_lines = compiled_requirements.read_text().splitlines()
#             compiled_requirements_lines = [line for line in compiled_requirements_lines if not line.startswith('#')]
#             save_path.write_text('\n'.join(compiled_requirements_lines))
#             log.info('ok / new requirements file copied to project.')
#         except Exception as e:
#             problem_message = f'Error copying new requirements file to project; error: ``{e}``'
#             log.exception(problem_message)

#         ## run git-pull ---------------------------------------------
#         """
#         Handles situation where ok=True, and stdout includes 'Already up to date', and stderr contains tag info.
#         """
#         call_result: tuple[bool, dict] = lib_git_handler.run_git_pull(project_path)
#         (ok, output) = call_result
#         if not ok:
#             if output['stderr']:
#                 problem_message += f'\nError with git-pull; stderr: ``{output["stderr"]}``'
#                 log.error(f'problem_message now, ``{problem_message}``')

#         ## run git-add ----------------------------------------------
#         call_result: tuple[bool, dict] = lib_git_handler.run_git_add(save_path, project_path)
#         (ok, output) = call_result
#         if output['stderr']:
#             problem_message += f'\nError with git-add; stderr: ``{output["stderr"]}``'
#             log.error(f'problem_message now, ``{problem_message}``')

#         ## run a git-commit via subprocess --------------------------
#         """
#         Handles `nothing to commit, working tree clean` situation, where ok=False, stderr is '', and stdout contains that message.
#         """
#         call_result: tuple[bool, dict] = lib_git_handler.run_git_commit(project_path)
#         (ok, output) = call_result
#         if output['stderr']:
#             problem_message += f'\nError with git-commit; stderr: ``{output["stderr"]}``'
#             log.error(f'problem_message now, ``{problem_message}``')

#         ## run a git-push via subprocess ----------------------------
#         """
#         Handles `Everything up-to-date` situation, where ok=True, stdout is '', and stderr contains that message.
#         """
#         call_result: tuple[bool, dict] = lib_git_handler.run_git_push(project_path)
#         (ok, output) = call_result
#         if not ok:
#             if output['stderr']:
#                 problem_message += f'\nError with git-push; stderr: ``{output["stderr"]}``'
#                 log.error(f'problem_message now, ``{problem_message}``')

#         log.debug(f'final problem_message: ``{problem_message}``')
#         return problem_message

#         ## end def copy_new_compile_to_codebase()

#     ## end class CompiledComparator
