import logging
import os
import pprint
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def parse_uv_lock_version_change(diff_text: str, package_name: str) -> tuple[bool, str | None, str | None]:
    """
    Parses a unified diff of uv.lock to detect a version change for a given package.

    Iterates line-by-line, tracking when inside a [[package]] block and reading
    the most recent name and version entries. Within the block where the package
    name matches (case-insensitive), captures pairs of -version/+version lines
    and compares their values. Returns early on positive detection.
    """
    in_package_block: bool = False
    current_package_name: str | None = None
    old_version: str | None = None
    new_version: str | None = None

    # Iterate through diff lines
    for raw_line in diff_text.splitlines():
        if not raw_line:
            continue

        # Determine diff marker and content; accept space, '-', '+'
        marker = raw_line[0]
        content = raw_line[1:] if marker in {' ', '+', '-'} else raw_line
        content = content.rstrip()  # keep potential leading symbol for effective marker detection

        # Compute effective marker: some diffs (or copied snippets) may have a leading space
        # followed by '-' or '+'. Normalize by inspecting first non-space char of content.
        stripped_leading = content.lstrip()
        leading_ws_len = len(content) - len(stripped_leading)
        effective_marker = marker
        if effective_marker == ' ' and stripped_leading[:1] in {'-', '+'}:
            effective_marker = stripped_leading[0]
            # Drop that symbol from content as well
            content = content[:leading_ws_len] + stripped_leading[1:]
        # Finally, normalize content for matching
        content = content.strip()

        # Detect start of a package block
        if content == '[[package]]':
            in_package_block = True
            current_package_name = None
            old_version = None
            new_version = None
            continue

        if not in_package_block:
            continue

        # Read package name when inside a block (allow any diff marker)
        if content.startswith('name ='):
            # Extract quoted value
            try:
                first_quote = content.index('"')
                second_quote = content.index('"', first_quote + 1)
                current_package_name = content[first_quote + 1:second_quote]
            except ValueError:
                current_package_name = None
            continue

        # Only inspect versions for the target package
        if (current_package_name or '').lower() != package_name.lower():
            # If we encounter another package block implicitly (context could end),
            # rely on explicit [[package]] lines to reset state.
            continue

        # Capture version removals/additions
        if effective_marker == '-' and content.startswith('version ='):
            try:
                first_quote = content.index('"')
                second_quote = content.index('"', first_quote + 1)
                old_version = content[first_quote + 1:second_quote]
            except ValueError:
                old_version = None
        elif effective_marker == '+' and content.startswith('version ='):
            try:
                first_quote = content.index('"')
                second_quote = content.index('"', first_quote + 1)
                new_version = content[first_quote + 1:second_quote]
            except ValueError:
                new_version = None

        # If both present, decide
        if old_version is not None and new_version is not None:
            if old_version != new_version:
                return True, old_version, new_version
            else:
                # Same version; continue scanning in case of subsequent changes,
                # but in practice unified diff won't emit both if identical.
                pass

    return False, old_version, new_version


def check_for_django_update(incoming_text: str) -> bool:
    """
    Checks if the uv.lock unified diff indicates a Django version update.
    """
    log.info('::: check_for_django_update ----------')
    updated, old_v, new_v = parse_uv_lock_version_change(incoming_text, 'django')
    if updated:
        log.info(f'ok / django version updated: {old_v} -> {new_v}')
        return True

    # Fallback: handle requirements.txt-style diffs e.g., lines with '+django=='
    incoming_lines: list[str] = incoming_text.split('\n')
    has_addition = any('+django==' in line for line in incoming_lines)
    has_removal = any('-django==' in line for line in incoming_lines)
    if has_addition and has_removal:
        log.info('ok / django version updated (requirements.txt style diff detected)')
        return True
    if has_addition:
        log.info('ok / django addition detected (requirements.txt style)')
        return True

    # Preserve the previous log shape for backward compatibility
    log.info('ok / django-updated, ``False``')
    return False


def run_collectstatic(project_path: Path, uv_path: Path) -> None | str:
    """
    Runs collectstatic command.
    """
    log.info('::: running collectstatic ----------')
    log.debug(f'cwd: {os.getcwd()}')
    command: list[str] = [
        str(uv_path),
        'run',
        './manage.py',
        'collectstatic',
        '--noinput',
        '--clear',
    ]
    log.debug(f'command: {command}')
    result: subprocess.CompletedProcess = subprocess.run(command, cwd=str(project_path), capture_output=True, text=True)
    log.debug(f'result: {result}')
    ok = True if result.returncode == 0 else False
    if ok is True:
        log.info('ok / collectstatic successful')
        problem_message = None
    else:
        log.info('problem / collectstatic failed; see log; problem message will be emailed')
        output = {'stdout': f'{result.stdout}', 'stderr': f'{result.stderr}'}
        problem_message = f'Problem running collectstatic; output, ``{pprint.pformat(output)}``'
    return problem_message


# def run_collectstatic(project_path: Path) -> None | str:
#     """
#     Runs collectstatic command.
#     """
#     log.info('::: running collectstatic ----------')
#     log.debug(f'cwd: {os.getcwd()}')
#     command = ['bash', '-c', 'source ../env/bin/activate && python ./manage.py collectstatic --noinput']
#     log.debug(f'command: {command}')
#     # subprocess.run(command, check=True)
#     result: subprocess.CompletedProcess = subprocess.run(command, cwd=str(project_path), capture_output=True, text=True)
#     log.debug(f'result: {result}')
#     ok = True if result.returncode == 0 else False
#     if ok is True:
#         log.info('ok / collectstatic successful')
#         problem_message = None
#     else:
#         log.info('problem / collectstatic failed; see log; problem message will be emailed')
#         output = {'stdout': f'{result.stdout}', 'stderr': f'{result.stderr}'}
#         problem_message = f'Problem running collectstatic; output, ``{pprint.pformat(output)}``'
#     return problem_message
