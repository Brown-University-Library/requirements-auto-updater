"""
See README.md for extensive info.
<https://github.com/Brown-University-Library/requirements-auto-updater/blob/main/README.md>

Info...
- Main manager function is`manage_update()`, at bottom above dundermain.
- Functions are in order called by `manage_update()`.

Usage...
`$ uv run ./auto_updater.py "/path/to/project_code_dir/"`
"""

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import TypedDict

from lib import lib_django_updater, lib_environment_checker
from lib.lib_call_runtests import run_followup_tests, run_initial_tests
from lib.lib_emailer import send_email_of_diffs
from lib.lib_git_handler import GitHandler
from lib.lib_uv_dry_run_classifier import DryRunClassification
from lib.lib_uv_updater import CompareResult, UvUpdater
from lib.lib_workflow_helpers import handle_staging_failure_rollback, run_django_followup

## load envars ------------------------------------------------------
this_file_path = Path(__file__).resolve()
stuff_dir = this_file_path.parent.parent

## define constants -------------------------------------------------
ENVAR_EMAIL_FROM = os.environ['AUTO_UPDTR__EMAIL_FROM']
ENVAR_EMAIL_HOST = os.environ['AUTO_UPDTR__EMAIL_HOST']
ENVAR_EMAIL_HOST_PORT = os.environ['AUTO_UPDTR__EMAIL_HOST_PORT']
UV_PATH = os.environ['AUTO_UPDTR__UV_PATH']
uv_path: Path = Path(UV_PATH).resolve()

## set up logging ---------------------------------------------------
log_dir: Path = stuff_dir / 'logs'
log_dir.mkdir(parents=True, exist_ok=True)
log_file_path: Path = log_dir / 'auto_updater.log'
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(levelname)s [%(module)s-%(funcName)s()::%(lineno)d] %(message)s',
    datefmt='%d/%b/%Y %H:%M:%S',
    filename=log_file_path,
)
log = logging.getLogger(__name__)


class PreflightData(TypedDict):
    """
    Shared validated data used by the environment-specific workflows.
    """

    project_path: Path
    project_email_addresses: list[tuple[str, str]]
    environment_type: str
    group: str


def update_group_and_permissions(project_path: Path, backup_file_path: Path | None, group: str) -> None:
    """
    Tries to update group-ownership and group-permissions for relevant directories.
    Intentionally does not fail if the commands fail.

    Called by manage_update().
    """
    log.info('::: updating group and permissions ----------')
    relative_env_path: Path = project_path / '.venv'
    venv_path: Path = relative_env_path.resolve()
    log.debug(f'env_path: ``{venv_path}``')
    target_paths: list[Path] = [venv_path]
    if backup_file_path is not None:
        target_paths.append(backup_file_path)
    for path in target_paths:
        log.debug(f'updating group and permissions for path: ``{path}``')
        chgrp_result: subprocess.CompletedProcess[str] = subprocess.run(
            ['chgrp', '-R', group, str(path)], capture_output=True, text=True, check=False
        )
        log.debug(f'chgrp_result: ``{chgrp_result}``')
        chmod_result: subprocess.CompletedProcess[str] = subprocess.run(
            ['chmod', '-R', 'g=rwX', str(path)], capture_output=True, text=True, check=False
        )
        log.debug(f'chmod_result: ``{chmod_result}``')
    log.info('ok / attempted update of group and permissions')
    return


def run_preflight_checks(project_path_str: str) -> PreflightData:
    """
    Runs shared setup and validation before branching into staging or production workflows.

    Called by manage_update().
    """
    ## validate project path ----------------------------------------
    project_path: Path = Path(project_path_str).resolve()
    lib_environment_checker.validate_project_path(project_path)
    ## cd to project dir --------------------------------------------
    os.chdir(project_path)
    ## get email addresses ------------------------------------------
    project_email_addresses: list[tuple[str, str]] = lib_environment_checker.determine_project_email_addresses(project_path)
    ## check branch -------------------------------------------------
    lib_environment_checker.check_branch(project_path, project_email_addresses)
    ## check git status ---------------------------------------------
    lib_environment_checker.check_git_status(project_path, project_email_addresses)
    ## validate pyproject.toml --------------------------------------
    lib_environment_checker.validate_pyproject_toml(project_path, project_email_addresses)
    ## get environment-type -----------------------------------------
    environment_type: str = lib_environment_checker.determine_environment_type(project_path, project_email_addresses)
    ## validate uv path ---------------------------------------------
    lib_environment_checker.validate_uv_path(uv_path, project_path)
    ## get group ----------------------------------------------------
    group: str = lib_environment_checker.determine_group(project_path, project_email_addresses)
    ## check for default directory ACLs -----------------------------
    lib_environment_checker.check_default_directory_facls(project_path, group, project_email_addresses)
    ## check for correct group and group-write permissions ----------
    lib_environment_checker.check_group_and_permissions(project_path, group, project_email_addresses)
    preflight_data = PreflightData(
        project_path=project_path,
        project_email_addresses=project_email_addresses,
        environment_type=environment_type,
        group=group,
    )
    return preflight_data


def run_staging_update_workflow(
    project_path: Path,
    project_email_addresses: list[tuple[str, str]],
    environment_type: str,
    uv_updater: UvUpdater,
) -> Path | None:
    """
    Runs the upgrade-oriented staging workflow.

    Called by manage_update().
    """
    uv_lock_backup_path: Path | None = None
    dry_run_classification: DryRunClassification = uv_updater.inspect_pending_sync(
        uv_path,
        project_path,
        environment_type,
        project_email_addresses,
    )
    if dry_run_classification['has_pending_change'] is False:
        log.info(dry_run_classification['summary'])
    elif dry_run_classification['is_exclude_newer_only'] is True:
        log.info(dry_run_classification['summary'])
    else:
        ## backup uv.lock --------------------------------------------
        uv_lock_backup_path = uv_updater.backup_uv_lock(uv_path, project_path)
        ## run uv sync -----------------------------------------------
        uv_updater.run_upgrade_sync(uv_path, project_path, environment_type, project_email_addresses)
        ## check if new uv.lock file is different --------------------
        compare_result: CompareResult = uv_updater.compare_uv_lock_files(project_path / 'uv.lock', uv_lock_backup_path)
        if compare_result['changes'] is True:
            ## check for django update -------------------------------
            diff_text: str = compare_result['diff']
            django_update: bool = lib_django_updater.check_for_django_update(diff_text)
            ## run django follow-up if needed ------------------------
            followup_collectstatic_problems: None | str = run_django_followup(project_path, uv_path, django_update)
            ## run post-update tests ---------------------------------
            followup_tests_problems: None | str = run_followup_tests(uv_path, project_path, environment_type)
            if followup_tests_problems is not None:
                ## handle test-failure rollback -----------------------
                handle_staging_failure_rollback(
                    project_path,
                    uv_path,
                    uv_updater,
                    diff_text,
                    followup_tests_problems,
                    project_email_addresses,
                )
                log.info('Skipping git operations due to test failure and rollback')
            else:
                ## git commit/push ------------------------------------
                git_handler = GitHandler()
                git_success, git_message = git_handler.manage_git(project_path, diff_text)
                followup_git_problems: None | str = None
                if git_success is False:
                    followup_git_problems = git_message
                    log.warning(f'Git operations failed: {git_message}')
                followup_problems = {
                    'collectstatic_problems': followup_collectstatic_problems,
                    'test_problems': followup_tests_problems,
                    'git_problems': followup_git_problems,
                }
                log.debug(f'followup_problems, ``{followup_problems}``')
                ## send diff email ------------------------------------
                send_email_of_diffs(project_path, diff_text, followup_problems, project_email_addresses)
                log.debug('email sent')
        else:
            log.info('No changes detected after substantive dry-run - skipping git operations')
    return uv_lock_backup_path


def run_production_sync_workflow(
    project_path: Path,
    project_email_addresses: list[tuple[str, str]],
    uv_updater: UvUpdater,
) -> None:
    """
    Runs the locked production sync workflow.

    Called by manage_update().
    """
    ## determine installed django version before sync ---------------
    django_before_version: str | None = lib_django_updater.find_installed_package_version(project_path, 'django')
    ## run locked sync ----------------------------------------------
    uv_updater.run_locked_sync(uv_path, project_path, 'production', project_email_addresses)
    ## determine installed django version after sync ----------------
    django_after_version: str | None = lib_django_updater.find_installed_package_version(project_path, 'django')
    ## run django follow-up if needed -------------------------------
    django_update: bool = lib_django_updater.did_package_version_change(django_before_version, django_after_version)
    run_django_followup(project_path, uv_path, django_update)
    return


def manage_update(project_path_str: str) -> None:
    """
    Main function to manage the update process for the project's dependencies.
    Note that `project_path_str` is not this project's path, but the path to the project to be updated.

    Called by __main__.
    """
    log.debug('starting manage_update()')
    ## run environmental checks -------------------------------------
    preflight_data: PreflightData = run_preflight_checks(project_path_str)
    project_path: Path = preflight_data['project_path']
    project_email_addresses: list[tuple[str, str]] = preflight_data['project_email_addresses']
    environment_type: str = preflight_data['environment_type']
    group: str = preflight_data['group']
    ## initial tests ------------------------------------------------
    run_initial_tests(uv_path, project_path, project_email_addresses, environment_type)
    uv_lock_backup_path: Path | None = None
    uv_updater = UvUpdater()
    if environment_type == 'production':
        ## production locked-sync workflow ---------------------------
        run_production_sync_workflow(project_path, project_email_addresses, uv_updater)
    else:
        ## staging upgrade workflow ---------------------------------
        uv_lock_backup_path = run_staging_update_workflow(
            project_path, project_email_addresses, environment_type, uv_updater
        )
    ## clean up -----------------------------------------------------
    update_group_and_permissions(project_path, uv_lock_backup_path, group)
    return


if __name__ == '__main__':
    log.debug('\n\nstarting dundermain')
    parser = argparse.ArgumentParser(description='Updates dependencies for the specified project')
    parser.add_argument('--project', required=True, help='Path to the project directory')
    try:
        args = parser.parse_args()
        project_path = args.project
        log.debug(f'Project path: {project_path}')
        manage_update(project_path)
    except argparse.ArgumentError as e:
        log.error(f'Argument error: {e}')
        parser.print_help()
        sys.exit(1)
