# /// script
# requires-python = "~=3.12.0"
# dependencies = ["python-dotenv"]
# ///

"""
See README.md for extensive info.
<https://github.com/Brown-University-Library/self_updater_code/blob/main/README.md>

Info...
- Main manager function is`manage_update()`, at bottom above dundermain.
- Functions are in order called by `manage_update()`.

Usage...
`$ uv run ./self_update.py "/path/to/project_code_dir/"`
"""

import difflib
import logging
import os
import smtplib
import socket
import subprocess
import sys
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

# ## add project to path ----------------------------------------------
this_file_path = Path(__file__).resolve()
stuff_dir = this_file_path.parent.parent
sys.path.append(str(stuff_dir))
from self_updater_code import environment_checker  # noqa: E402  (prevents linter problem-indicator)

## load envars ------------------------------------------------------
dotenv_path = stuff_dir / '.env'
assert dotenv_path.exists(), f'file does not exist, ``{dotenv_path}``'
load_dotenv(find_dotenv(str(dotenv_path), raise_error_if_not_found=True), override=True)

## define constants -------------------------------------------------
ENVAR_EMAIL_FROM = os.environ['SLFUPDTR__EMAIL_FROM']
ENVAR_EMAIL_HOST = os.environ['SLFUPDTR__EMAIL_HOST']
ENVAR_EMAIL_HOST_PORT = os.environ['SLFUPDTR__EMAIL_HOST_PORT']

## set up logging ---------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(levelname)s [%(module)s-%(funcName)s()::%(lineno)d] %(message)s',
    datefmt='%d/%b/%Y %H:%M:%S',
)
log = logging.getLogger(__name__)


## ------------------------------------------------------------------
## main code -- called by manage_update() ---------------------------
## ------------------------------------------------------------------


def compile_requirements(project_path: Path, python_version: str, environment_type: str, uv_path: Path) -> Path:
    """
    Compiles the project's `requirements.in` file into a versioned `requirements.txt` backup.
    Returns the path to the newly created backup file.
    """
    log.debug('starting compile_requirements()')
    ## prepare requirements.in filepath -----------------------------
    requirements_in: Path = project_path / 'requirements' / f'{environment_type}.in'  # local.in, staging.in, production.in
    log.debug(f'requirements.in path, ``{requirements_in}``')
    ## ensure backup-directory is ready -----------------------------
    backup_dir: Path = project_path.parent / 'requirements_backups'
    log.debug(f'backup_dir: ``{backup_dir}``')
    backup_dir.mkdir(parents=True, exist_ok=True)
    ## prepare compiled_filepath ------------------------------------
    timestamp: str = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
    compiled_filepath: Path = backup_dir / f'{environment_type}_{timestamp}.txt'
    log.debug(f'backup_file: ``{compiled_filepath}``')
    ## prepare compile command --------------------------------------
    compile_command: list[str] = [
        str(uv_path),
        'pip',
        'compile',
        str(requirements_in),
        '--output-file',
        str(compiled_filepath),
        '--universal',
        '--python',
        python_version,
    ]
    log.debug(f'compile_command: ``{compile_command}``')
    ## run compile command ------------------------------------------
    try:
        subprocess.run(compile_command, check=True)
        log.debug('uv pip compile was successful')
    except subprocess.CalledProcessError:
        message = 'Error during pip compile'
        log.exception(message)
        raise Exception(message)
    return compiled_filepath

    ## end def compile_requirements()


def remove_old_backups(project_path: Path, keep_recent: int = 30) -> None:
    """
    Removes all files in the backup directory other than the most-recent files.
    """
    log.debug('starting remove_old_backups()')
    backup_dir: Path = project_path.parent / 'requirements_backups'
    backups: list[Path] = sorted([f for f in backup_dir.iterdir() if f.is_file() and f.suffix == '.txt'], reverse=True)
    old_backups: list[Path] = backups[keep_recent:]

    for old_backup in old_backups:
        log.debug(f'removing old backup: {old_backup}')
        old_backup.unlink()
    return


def compare_with_previous_backup(new_path: Path, old_path: Path | None = None, project_path: Path | None = None) -> bool:
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
            curr_lines_filtered = filter_initial_comments(curr_lines)  # removes initial comments
            prev_lines_filtered = filter_initial_comments(prev_lines)  # removes initial comments
            if curr_lines_filtered == prev_lines_filtered:
                log.debug('no differences found in dependencies.')
                changes = False
    log.debug(f'changes: ``{changes}``')
    return changes  # just the boolean


def sync_dependencies(project_path: Path, backup_file: Path, uv_path: Path) -> None:
    """
    Prepares the venv environment.
    Syncs the recent `--output` requirements.in file to the venv.
    Exits the script if any command fails.

    Why this works, without explicitly "activate"-ing the venv...

    When a Python virtual environment is traditionally 'activated' -- ie via `source venv/bin/activate`
    in a shell -- what is really happening is that a set of environment variables is adjusted
    to ensure that when python or other commands are run, they refer to the virtual environment's
    binaries and site-packages rather than the system-wide python installation.

    This code mimicks that environment modification by explicitly setting
    the PATH and VIRTUAL_ENV environment variables before running the command.
    """
    log.debug('starting activate_and_sync_dependencies()')
    ## prepare env-path variables -----------------------------------
    venv_bin_path: Path = project_path.parent / 'env' / 'bin'
    venv_path: Path = project_path.parent / 'env'
    log.debug(f'venv_bin_path: ``{venv_bin_path}``')
    log.debug(f'venv_path: ``{venv_path}``')
    ## set the local-env paths ---------------------------------------
    local_scoped_env = os.environ.copy()
    local_scoped_env['PATH'] = f'{venv_bin_path}:{local_scoped_env["PATH"]}'  # prioritizes venv-path
    local_scoped_env['VIRTUAL_ENV'] = str(venv_path)
    ## prepare sync command ------------------------------------------
    sync_command: list[str] = [str(uv_path), 'pip', 'sync', str(backup_file)]
    log.debug(f'sync_command: ``{sync_command}``')
    try:
        ## run sync command ------------------------------------------
        subprocess.run(sync_command, check=True, env=local_scoped_env)  # so all installs will go to the venv
        log.debug('uv pip sync was successful')
    except subprocess.CalledProcessError:
        message = 'Error during pip sync'
        log.exception(message)
        raise Exception(message)
    try:
        ## run `touch` to make the changes take effect ---------------
        subprocess.run(['touch', './config/tmp/restart.txt'], check=True)
        log.debug('ran `touch`')
    except subprocess.CalledProcessError:
        message = 'Error during pip sync or touch'
        log.exception(message)
        raise Exception(message)
    return

    ## end def sync_dependencies()


def mark_active(backup_file: Path) -> None:
    """
    Marks the backup file as active by adding a header comment.
    """
    log.debug('starting mark_active()')
    with backup_file.open('r') as file:
        content: list[str] = file.readlines()
    content.insert(0, '# ACTIVE\n')

    with backup_file.open('w') as file:
        file.writelines(content)
    return


def send_email_of_diffs(project_path: Path, email_addresses: list[list[str, str]]) -> None:
    """
    Sends an email with the differences between the previous and current requirements files.
    """
    log.debug('starting send_email_of_diffs()')
    log.debug(f'email_addresses: ``{email_addresses}``')
    ## generate diff ------------------------------------------------
    diff_text: str = make_diff_text(project_path)
    ## prep email data ----------------------------------------------
    EMAIL_HOST = ENVAR_EMAIL_HOST
    log.debug(f'EMAIL_HOST: ``{EMAIL_HOST}``')
    EMAIL_PORT = int(ENVAR_EMAIL_HOST_PORT)
    EMAIL_FROM = ENVAR_EMAIL_FROM
    recipients = []
    for name, email in email_addresses:
        recipients.append(f'"{name}" <{email}>')
    log.debug(f'recipients: {recipients}')
    EMAIL_RECIPIENTS = recipients
    HOST = socket.gethostname()
    log.debug(f'HOST: ``{HOST}``')  # if this is the same as EMAIL_HOST, combine.
    BODY = f'The dependencies for {project_path.name} have changed. The differences are:\n\n{diff_text}'
    ## build email message ------------------------------------------
    eml = MIMEText(f'{BODY}')
    eml['Subject'] = f'bul-self-updater info from ``{HOST.upper()}`` for project ``{project_path.name}``'
    eml['From'] = EMAIL_FROM
    eml['To'] = ', '.join(EMAIL_RECIPIENTS)
    ## send email ---------------------------------------------------
    try:
        s = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        s.sendmail(EMAIL_FROM, EMAIL_RECIPIENTS, eml.as_string())
    except Exception as e:
        err = repr(e)
        log.exception(f'problem sending self-updater mail, ``{err}``')
        raise Exception(err)
    return


def update_permissions(project_path: Path, backup_file: Path, group: str) -> None:
    """
    Update group ownership and permissions for relevant directories.
    Mark the backup file as active by adding a header comment.
    """
    log.debug('starting update_permissions_and_mark_active()')
    # group: str = infer_group(project_path)
    backup_dir: Path = project_path.parent / 'requirements_backups'
    log.debug(f'backup_dir: ``{backup_dir}``')
    relative_env_path = project_path / '../env'
    env_path = relative_env_path.resolve()
    log.debug(f'env_path: ``{env_path}``')
    for path in [env_path, backup_dir]:
        log.debug(f'updating group and permissions for path: ``{path}``')
        subprocess.run(['chgrp', '-R', group, str(path)], check=True)
        subprocess.run(['chmod', '-R', 'g=rwX', str(path)], check=True)
    return


## ------------------------------------------------------------------
## helper functions (called by code above) --------------------------
## ------------------------------------------------------------------


def filter_initial_comments(lines: list[str]) -> list[str]:
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


def make_diff_text(project_path: Path) -> str:
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
        curr_lines_filtered = filter_initial_comments(curr_lines)  # removes initial comments
        prev_lines_filtered = filter_initial_comments(prev_lines)  # removes initial comments
        ## build the diff info --------------------------------------
        diff_lines = [f'--- {previous_file.name}\n', f'+++ {current_file.name}\n']
        diff_lines.extend(difflib.unified_diff(prev_lines_filtered, curr_lines_filtered))
        diff_text = ''.join(diff_lines)
    log.debug(f'diff_text: ``{diff_text}``')
    return diff_text


## ------------------------------------------------------------------
## main manager function --------------------------------------------
## ------------------------------------------------------------------


def manage_update(project_path: str) -> None:
    """
    Main function to manage the update process for the project's dependencies.
    Calls various helper functions to validate, compile, compare, sync, and update permissions.
    """
    log.debug('starting manage_update()')
    ## validate project path ----------------------------------------
    project_path: Path = Path(project_path).resolve()  # ensures an absolute path now
    environment_checker.validate_project_path(project_path)
    ## cd to project dir --------------------------------------------
    os.chdir(project_path)
    ## get everything needed up front -------------------------------
    python_version: str = environment_checker.determine_python_version(project_path)  # for compiling requirements
    environment_type: str = environment_checker.determine_environment_type()  # for compiling requirements
    uv_path: Path = environment_checker.determine_uv_path()
    email_addresses: list[list[str, str]] = environment_checker.determine_email_addresses()
    group: str = environment_checker.determine_group(project_path)
    ## compile requirements file ------------------------------------
    compiled_requirements: Path = compile_requirements(project_path, python_version, environment_type, uv_path)
    ## cleanup old backups ------------------------------------------
    remove_old_backups(project_path)
    ## see if the new compile is different --------------------------
    # differences_found: bool = compare_with_previous_backup(project_path)
    differences_found: bool = compare_with_previous_backup(compiled_requirements, old_path=None, project_path=project_path)
    if not differences_found:
        log.debug('no differences found in dependencies.')
    else:
        ## since it's different, update the venv --------------------
        log.debug('differences found in dependencies; updating venv')
        sync_dependencies(project_path, compiled_requirements, uv_path)
        log.debug('dependencies updated successfully.')
        ## mark new-compile as active -------------------------------
        mark_active(compiled_requirements)
        ## send diff email ------------------------------------------
        send_email_of_diffs(project_path, email_addresses)
        log.debug('email sent')
    ## update group and permissions ---------------------------------
    update_permissions(project_path, compiled_requirements, group)
    return

    ## end def manage_update()


if __name__ == '__main__':
    log.debug('starting dundermain')
    if len(sys.argv) != 2:
        print('Usage: python update_packages.py <project_path>')
        sys.exit(1)

    project_path: str = sys.argv[1]
    manage_update(project_path)
