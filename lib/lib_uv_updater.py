"""
Module used by auto_updater.py.
Contains helpers for dry-run inspection, sync execution, rollback, and uv.lock comparison.
"""

import difflib
import logging
import pprint
import shutil
import subprocess
from pathlib import Path
from typing import TypedDict

from lib.lib_call_runtests import make_run_tests_command, run_run_tests_command, should_run_tests
from lib.lib_emailer import Emailer
from lib.lib_uv_dry_run_classifier import DryRunClassification, classify_dry_run_output

log = logging.getLogger(__name__)


class CompareResult(TypedDict):
    """
    Structured result for comparing uv.lock with its backup.
    """

    changes: bool
    diff: str


class DryRunResult(TypedDict):
    """
    Structured result for running uv sync in dry-run mode.
    """

    ok: bool
    stdout: str
    stderr: str
    classification: DryRunClassification | None


class CommandResult(TypedDict):
    """
    Structured result for a generic subprocess command.
    """

    ok: bool
    stdout: str
    stderr: str


class UvUpdater:
    def resolve_dependency_group(self, environment_type: str) -> str:
        """
        Maps the environment type to the project's uv dependency group name.

        Called by make_upgrade_sync_command().
        Called by make_locked_sync_command().
        Called by make_restore_sync_command().
        """
        group_map: dict[str, str] = {
            'local': 'local',
            'staging': 'staging',
            'production': 'prod',
        }
        if environment_type not in group_map:
            msg = f'Invalid environment_type: {environment_type}'
            log.exception(msg)
            raise Exception(msg)
        group: str = group_map[environment_type]
        return group

    def inspect_pending_sync(
        self,
        uv_path: Path,
        project_path: Path,
        environment_type: str,
        project_email_addresses: list[tuple[str, str]],
    ) -> DryRunClassification:
        """
        Runs the staging dry-run upgrade check and returns a structured classification result.

        Called by auto_updater.run_staging_update_workflow().
        """
        dry_run_command: list[str] = self.make_upgrade_dry_run_command(uv_path, environment_type)
        dry_run_result: DryRunResult = self.run_dry_run_sync_command(dry_run_command, project_path)
        if dry_run_result['ok'] is True and dry_run_result['classification'] is not None:
            classification: DryRunClassification = dry_run_result['classification']
            return classification
        problem_details: list[str] = ['problem / uv dry-run sync failed']
        problem_details.append(f'command: {dry_run_command}')
        problem_details.append(f'stdout: {dry_run_result["stdout"]}')
        problem_details.append(f'stderr: {dry_run_result["stderr"]}')
        problem_message: str = '\n'.join(problem_details)
        self.email_setup_problem(project_path, project_email_addresses, problem_message)
        raise Exception(problem_message)

    def run_upgrade_sync(
        self,
        uv_path: Path,
        project_path: Path,
        environment_type: str,
        project_email_addresses: list[tuple[str, str]],
    ) -> None:
        """
        Runs the upgrade-oriented sync used by staging.

        Called by auto_updater.run_staging_update_workflow().
        """
        log.info('::: starting upgrade uv sync ----------')
        sync_command: list[str] = self.make_upgrade_sync_command(uv_path, environment_type)
        sync_result: CommandResult = self.run_sync_command(sync_command, project_path)
        if sync_result['ok'] is False:
            problem_details: list[str] = ['problem / upgrade uv sync failed']
            problem_details.append(f'command: {sync_command}')
            problem_details.append(f'stdout: {sync_result["stdout"]}')
            problem_details.append(f'stderr: {sync_result["stderr"]}')
            problem_message: str = '\n'.join(problem_details)
            self.restore_uv_lock_from_backup(project_path)
            restore_problem: None | str = self.restore_staging_environment(uv_path, project_path)
            if restore_problem is not None:
                problem_details.append(restore_problem)
            rollback_test_problem: None | str = self.verify_staging_rollback(uv_path, project_path, environment_type)
            if rollback_test_problem is not None:
                problem_details.append(rollback_test_problem)
            problem_message = '\n'.join(problem_details)
            self.email_setup_problem(project_path, project_email_addresses, problem_message)
            raise Exception(problem_message)
        return

    def run_locked_sync(
        self,
        uv_path: Path,
        project_path: Path,
        environment_type: str,
        project_email_addresses: list[tuple[str, str]],
    ) -> None:
        """
        Runs the production locked sync that realizes the committed uv.lock.

        Called by auto_updater.run_production_sync_workflow().
        """
        log.info('::: starting locked uv sync ----------')
        sync_command: list[str] = self.make_locked_sync_command(uv_path, environment_type)
        sync_result: CommandResult = self.run_sync_command(sync_command, project_path)
        if sync_result['ok'] is False:
            problem_details: list[str] = ['problem / locked uv sync failed']
            problem_details.append(f'command: {sync_command}')
            problem_details.append(f'stdout: {sync_result["stdout"]}')
            problem_details.append(f'stderr: {sync_result["stderr"]}')
            problem_message: str = '\n'.join(problem_details)
            self.email_setup_problem(project_path, project_email_addresses, problem_message)
            raise Exception(problem_message)
        return

    def backup_uv_lock(self, uv_path: Path, project_path: Path) -> Path:
        """
        Backs up the uv.lock file.

        Called by auto_updater.run_staging_update_workflow().
        """
        assert isinstance(uv_path, Path), f'type(uv_path) is {type(uv_path)}'
        uv_lock_path: Path = project_path / 'uv.lock'
        backup_file_path: Path = project_path.parent / 'uv.lock.bak'
        shutil.copy(uv_lock_path, backup_file_path)
        assert backup_file_path.exists(), f'backup_file_path does not exist, ``{backup_file_path}``'
        return backup_file_path

    def restore_uv_lock_from_backup(self, project_path: Path) -> None:
        """
        Restores uv.lock from the standard backup file.

        Called by run_upgrade_sync().
        """
        shutil.copy(project_path.parent / 'uv.lock.bak', project_path / 'uv.lock')
        log.info('Restored uv.lock from backup')
        return

    def restore_staging_environment(self, uv_path: Path, project_path: Path) -> None | str:
        """
        Restores the staging .venv from the backed-up uv.lock.

        Called by run_upgrade_sync().
        Called by lib_workflow_helpers.handle_staging_failure_rollback().
        """
        sync_command: list[str] = self.make_restore_sync_command(uv_path, 'staging')
        restore_result: CommandResult = self.run_sync_command(sync_command, project_path)
        problem_message: None | str = None
        if restore_result['ok'] is False:
            error_output = {'stdout': restore_result['stdout'], 'stderr': restore_result['stderr']}
            log.debug(f'error_output, ``{pprint.pformat(error_output)}``')
            problem_message = 'problem: restoring previous uv sync failed; see log output.'
        return problem_message

    def verify_staging_rollback(self, uv_path: Path, project_path: Path, environment_type: str) -> None | str:
        """
        Re-runs tests after a staging rollback to confirm the environment is healthy.

        Called by run_upgrade_sync().
        """
        problem_message: None | str = None
        if should_run_tests(environment_type):
            run_tests_command: list[str] = make_run_tests_command(project_path, uv_path)
            tests_ok, tests_output = run_run_tests_command(run_tests_command, project_path)
            if tests_ok is False:
                problem_message = f'Error on rollback run_tests() call: {tests_output}'
        else:
            log.info('Production environment detected - skipping rollback tests')
        return problem_message

    def make_upgrade_dry_run_command(self, uv_path: Path, environment_type: str) -> list[str]:
        """
        Makes the staging dry-run upgrade command.

        Called by inspect_pending_sync().
        """
        command: list[str] = self.make_upgrade_sync_command(uv_path, environment_type)
        command.extend(['--dry-run', '--output-format', 'json'])
        log.debug(f'dry-run cmnd, ``{command}``')
        return command

    def make_upgrade_sync_command(self, uv_path: Path, environment_type: str) -> list[str]:
        """
        Makes the upgrade-oriented sync command.

        Called by run_upgrade_sync().
        Called by make_upgrade_dry_run_command().
        """
        group: str = self.resolve_dependency_group(environment_type)
        command: list[str] = [str(uv_path), 'sync', '--no-active', '--upgrade', '--group', group]
        log.debug(f'command, ``{command}``')
        return command

    def make_locked_sync_command(self, uv_path: Path, environment_type: str) -> list[str]:
        """
        Makes the production locked sync command.

        Called by run_locked_sync().
        """
        group: str = self.resolve_dependency_group(environment_type)
        command: list[str] = [str(uv_path), 'sync', '--no-active', '--locked', '--group', group]
        log.debug(f'command, ``{command}``')
        return command

    def make_restore_sync_command(self, uv_path: Path, environment_type: str) -> list[str]:
        """
        Makes the rollback restore sync command.

        Called by restore_staging_environment().
        """
        group: str = self.resolve_dependency_group(environment_type)
        command: list[str] = [str(uv_path), 'sync', '--no-active', '--frozen', '--group', group]
        log.debug(f'command, ``{command}``')
        return command

    def run_sync_command(self, sync_command: list[str], project_path: Path) -> CommandResult:
        """
        Runs a uv sync command and captures stdout/stderr.

        Called by run_upgrade_sync().
        Called by run_locked_sync().
        Called by restore_staging_environment().
        """
        result: subprocess.CompletedProcess[str] = subprocess.run(
            sync_command, cwd=str(project_path), capture_output=True, text=True
        )
        log.debug(f'result: {result}')
        ok: bool = result.returncode == 0
        if ok is True:
            log.info('ok / uv sync successful')
        else:
            log.info('problem / uv sync failed')
        command_result = CommandResult(ok=ok, stdout=f'{result.stdout}', stderr=f'{result.stderr}')
        return command_result

    def run_dry_run_sync_command(self, sync_command: list[str], project_path: Path) -> DryRunResult:
        """
        Runs uv sync in dry-run mode and classifies the result.

        Called by inspect_pending_sync().
        """
        log.info('::: running uv sync dry-run ----------')
        result: subprocess.CompletedProcess[str] = subprocess.run(
            sync_command, cwd=str(project_path), capture_output=True, text=True
        )
        ok: bool = result.returncode == 0
        stdout: str = f'{result.stdout}'
        stderr: str = f'{result.stderr}'
        combined_output: str = f'{stdout}\n{stderr}'.strip()
        classification: DryRunClassification | None = None
        if ok is True:
            classification = classify_dry_run_output(combined_output)
            log.info(f'ok / dry-run classification: {classification["summary"]}')
        else:
            log.info('problem / uv sync dry-run failed')
        dry_run_result = DryRunResult(
            ok=ok,
            stdout=stdout,
            stderr=stderr,
            classification=classification,
        )
        return dry_run_result

    def email_setup_problem(
        self,
        project_path: Path,
        project_email_addresses: list[tuple[str, str]],
        problem_message: str,
    ) -> None:
        """
        Emails project admins about a sync/setup problem.

        Called by inspect_pending_sync().
        Called by run_upgrade_sync().
        Called by run_locked_sync().
        """
        emailer = Emailer(project_path)
        email_message: str = emailer.create_setup_problem_message(problem_message)
        emailer.send_email(project_email_addresses, email_message)
        return

    def compare_uv_lock_files(self, uv_lock_path: Path, uv_lock_backup_path: Path) -> CompareResult:
        """
        Compares the current uv.lock file with its backup and returns a structured result.

        Called by auto_updater.run_staging_update_workflow().
        """
        log.info('::: comparing uv.lock files ----------')
        try:
            with uv_lock_path.open() as curr, uv_lock_backup_path.open() as prev:
                curr_lines = [line.rstrip() for line in curr.readlines()]
                prev_lines = [line.rstrip() for line in prev.readlines()]
                diff: list[str] = list(
                    difflib.unified_diff(
                        prev_lines,
                        curr_lines,
                        fromfile=str(uv_lock_backup_path),
                        tofile=str(uv_lock_path),
                        lineterm='',
                    )
                )
                log.debug(f'diff: \n{pprint.pformat(diff)}')
                if diff:
                    log.info('ok / differences found between uv.lock and its backup')
                else:
                    log.info('ok / no differences found between uv.lock and its backup')
            diff_text: str = '\n'.join(diff) + '\n'
            log.debug(f'diff_text: \n{diff_text}')
            changes: bool = bool(diff)
            compare_result = CompareResult(changes=changes, diff=diff_text)
        except Exception as e:
            log.error(f'Error comparing uv.lock files: {str(e)}')
            compare_result = CompareResult(changes=False, diff='')
        return compare_result
