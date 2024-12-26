import difflib
import logging
from pathlib import Path

## set up logging ---------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(levelname)s [%(module)s-%(funcName)s()::%(lineno)d] %(message)s',
    datefmt='%d/%b/%Y %H:%M:%S',
)
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

    ## end class CompiledComparator
