import logging
import shutil
import subprocess
from pathlib import Path

from lib import lib_django_updater
from lib.lib_call_runtests import run_followup_tests
from lib.lib_emailer import send_email_of_diffs
from lib.lib_uv_updater import UvUpdater

log = logging.getLogger(__name__)


def run_django_followup(project_path: Path, uv_path: Path, django_update: bool) -> None | str:
    """
    Runs Django follow-up commands when a Django update has been activated.

    Called by auto_updater.run_staging_update_workflow().
    Called by auto_updater.run_production_sync_workflow().
    """
    problem_message: None | str = None
    if django_update is True:
        ## run collectstatic -----------------------------------------
        problem_message = lib_django_updater.run_collectstatic(project_path, uv_path)
        ## trigger app reload ----------------------------------------
        subprocess.run(['touch', './config/tmp/restart.txt'], cwd=str(project_path), check=True)
    return problem_message


def handle_staging_failure_rollback(
    project_path: Path,
    uv_path: Path,
    uv_updater: UvUpdater,
    diff_text: str,
    followup_tests_problems: str,
    project_email_addresses: list[tuple[str, str]],
) -> None:
    """
    Restores the original lockfile and environment after a staging post-update test failure.

    Called by auto_updater.run_staging_update_workflow().
    """
    log.warning('Post-update tests failed; initiating rollback')
    ## restore original uv.lock from backup -------------------------
    backup_path: Path = project_path.parent / 'uv.lock.bak'
    shutil.copy(backup_path, project_path / 'uv.lock')
    log.info('Restored original uv.lock from backup')
    ## sync .venv from restored uv.lock -----------------------------
    uv_updater.restore_staging_environment(uv_path, project_path)
    ## re-run tests to verify restoration worked --------------------
    verification_result: None | str = run_followup_tests(uv_path, project_path, 'staging')
    if verification_result is not None:
        log.error('Tests still failing after rollback - environment may be corrupted')
    else:
        log.info('Tests passing after rollback - environment successfully restored')
    rollback_problems: dict[str, object] = {
        'collectstatic_problems': None,
        'test_problems': followup_tests_problems,
        'git_problems': None,
        'rollback_occurred': True,
        'verification_result': verification_result,
    }
    ## email about rollback -----------------------------------------
    send_email_of_diffs(project_path, diff_text, rollback_problems, project_email_addresses)
    log.info('Rollback email sent')
    return
