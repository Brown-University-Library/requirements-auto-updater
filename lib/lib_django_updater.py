import logging
import os
import pprint
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def check_for_django_update(incoming_text: str) -> bool:
    """
    Checks if the uv.lock unified diff indicates a Django version update.
    Called by auto_updater.manage_update().
    """
    log.info('::: check_for_django_update ----------')
    updated, old_v, new_v = parse_uv_lock_version_change(incoming_text, 'django')
    if updated:
        log.info(f'ok / django version updated: {old_v} -> {new_v}')
        return True
    else:
        log.info('ok / django-updated, ``False``')
        return False


def _extract_first_quoted_value(line: str) -> str | None:
    """
    Extracts the first double-quoted value from a TOML-like assignment line.

    Returns None when the line does not contain a pair of double quotes.
    """
    first_quote: int = line.find('"')
    if first_quote == -1:
        return None

    second_quote: int = line.find('"', first_quote + 1)
    if second_quote == -1:
        return None

    return line[first_quote + 1 : second_quote]


def parse_uv_lock_version_change(
    diff_text: str,
    package_name: str,
) -> tuple[bool, str | None, str | None]:
    """
    Parses a unified diff of uv.lock to detect a version change for a given package.

    Tracks when inside a [[package]] block, reads the most recent name entry, and
    (within the matching package block) captures -version/+version values.
    """
    in_package_block: bool = False
    current_package_name: str | None = None
    old_version: str | None = None
    new_version: str | None = None
    found_change: bool = False

    target_name: str = package_name.lower()

    for raw_line in diff_text.splitlines():
        if not raw_line:
            continue

        marker: str = raw_line[0]
        has_diff_marker: bool = marker in {' ', '+', '-'}

        # In a normal unified diff, only these three markers represent file content.
        # Non-marker lines (diff headers, @@ hunks, etc.) are ignored by content checks anyway.
        content: str = raw_line[1:] if has_diff_marker else raw_line
        content = content.strip()

        if content == '[[package]]':
            in_package_block = True
            current_package_name = None
            old_version = None
            new_version = None
            continue

        if not in_package_block:
            continue

        if content.startswith('name ='):
            current_package_name = _extract_first_quoted_value(content)
            continue

        if (current_package_name or '').lower() != target_name:
            continue

        if marker == '-' and content.startswith('version ='):
            old_version = _extract_first_quoted_value(content)
        elif marker == '+' and content.startswith('version ='):
            new_version = _extract_first_quoted_value(content)

        if old_version is not None and new_version is not None and old_version != new_version:
            found_change = True
            break

    return found_change, old_version, new_version


# def parse_uv_lock_version_change(diff_text: str, package_name: str) -> tuple[bool, str | None, str | None]:
#     """
#     Parses a unified diff of uv.lock to detect a version change for a given package.

#     Iterates line-by-line, tracking when inside a [[package]] block and reading
#     the most recent name and version entries. Within the block where the package
#     name matches (case-insensitive), captures pairs of -version/+version lines
#     and compares their values. Returns early on positive detection.

#     Called by check_for_django_update().
#     Mostly created by Windsurf's `GPT-5 (low-reasoning)`.
#     """
#     ## setup vars
#     in_package_block: bool = False
#     current_package_name: str | None = None
#     old_version: str | None = None
#     new_version: str | None = None

#     ## Iterate through diff lines
#     for raw_line in diff_text.splitlines():
#         if not raw_line:
#             continue

#         ## Determine diff marker and content; accept space, '-', '+'
#         marker = raw_line[0]
#         content = raw_line[1:] if marker in {' ', '+', '-'} else raw_line
#         content = content.rstrip()  # keep potential leading symbol for effective marker detection

#         ## Compute effective marker: some diffs (or copied snippets) may have a leading space
#         ## followed by '-' or '+'. Normalize by inspecting first non-space char of content.
#         stripped_leading = content.lstrip()
#         leading_ws_len = len(content) - len(stripped_leading)
#         effective_marker = marker
#         if effective_marker == ' ' and stripped_leading[:1] in {'-', '+'}:
#             effective_marker = stripped_leading[0]
#             # Drop that symbol from content as well
#             content = content[:leading_ws_len] + stripped_leading[1:]
#         # Finally, normalize content for matching
#         content = content.strip()

#         # Detect start of a package block
#         if content == '[[package]]':
#             in_package_block = True
#             current_package_name = None
#             old_version = None
#             new_version = None
#             continue

#         if not in_package_block:
#             continue

#         # Read package name when inside a block (allow any diff marker)
#         if content.startswith('name ='):
#             # Extract quoted value
#             try:
#                 first_quote = content.index('"')
#                 second_quote = content.index('"', first_quote + 1)
#                 current_package_name = content[first_quote + 1 : second_quote]
#             except ValueError:
#                 current_package_name = None
#             continue

#         # Only inspect versions for the target package
#         if (current_package_name or '').lower() != package_name.lower():
#             # If we encounter another package block implicitly (context could end),
#             # rely on explicit [[package]] lines to reset state.
#             continue

#         # Capture version removals/additions
#         if effective_marker == '-' and content.startswith('version ='):
#             try:
#                 first_quote = content.index('"')
#                 second_quote = content.index('"', first_quote + 1)
#                 old_version = content[first_quote + 1 : second_quote]
#             except ValueError:
#                 old_version = None
#         elif effective_marker == '+' and content.startswith('version ='):
#             try:
#                 first_quote = content.index('"')
#                 second_quote = content.index('"', first_quote + 1)
#                 new_version = content[first_quote + 1 : second_quote]
#             except ValueError:
#                 new_version = None

#         # If both present, decide
#         if old_version is not None and new_version is not None:
#             if old_version != new_version:
#                 return True, old_version, new_version
#             else:
#                 # Same version; continue scanning in case of subsequent changes,
#                 # but in practice unified diff won't emit both if identical.
#                 pass

#     return False, old_version, new_version

#     ## end def parse_uv_lock_version_change()


def run_collectstatic(project_path: Path, uv_path: Path) -> None | str:
    """
    Runs collectstatic command.
    Called by auto_updater.manage_update().
    """
    log.info('::: running collectstatic ----------')
    log.debug(f'cwd: {os.getcwd()}')
    command: list[str] = [
        str(uv_path),
        'run',
        './manage.py',
        'collectstatic',
        '--noinput',
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
