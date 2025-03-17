"""
Checks for correct group and permissions on files in two directories.
"""

import grp
import logging
import pathlib
import pprint
import stat

log = logging.getLogger(__name__)


def check_group(item: pathlib.Path, expected_group: str) -> str | None:
    """
    Helper function; checks if the group of the given item is the expected group.
    Called by check_files().
    """
    try:
        item_group: str = grp.getgrgid(item.stat().st_gid).gr_name
    except Exception as err:
        return f'Cannot determine group: {err}'

    if item_group != expected_group:
        return f'Incorrect group: expected {expected_group}, got {item_group}'
    return None


def check_permissions(item: pathlib.Path) -> str | None:
    """
    Helper function; checks if the item is group-writeable.
    Called by check_files().
    """
    try:
        st_mode: int = item.stat().st_mode
    except Exception as err:
        return f'Cannot stat: {err}'

    if not (st_mode & stat.S_IWGRP):
        return 'Not group-writeable'
    return None


def check_files(path: pathlib.Path, expected_group: str) -> dict[str, list[str]]:
    """
    Main function; checks the group and permissions of all files in the given path.
    Called by lib_environment_checker.check_group_and_permissions().
    """
    problems: dict[str, list[str]] = {}

    items: list[pathlib.Path] = sorted(path.rglob('*'))
    for item in items:
        if item.is_symlink():
            continue  # skip symlinks

        item_problems: list[str] = []

        group_issue: str | None = check_group(item, expected_group)
        if group_issue:
            item_problems.append(group_issue)

        permission_issue: str | None = check_permissions(item)
        if permission_issue:
            item_problems.append(permission_issue)

        if item_problems:
            problems[str(item)] = item_problems
    log.debug(f'problems, ``{pprint.pformat(problems)}``')
    return problems


# def check_files(path: pathlib.Path, expected_group: str) -> dict[pathlib.Path, list[str]]:
#     """
#     Main function; checks the group and permissions of all files in the given path.
#     Called by lib_environment_checker.check_group_and_permissions().
#     """
#     problems: dict[pathlib.Path, list[str]] = {}

#     items: list[pathlib.Path] = sorted(path.rglob('*'))
#     for item in items:
#         if item.is_symlink():
#             continue  # skip symlinks

#         item_problems: list[str] = []

#         group_issue: str | None = check_group(item, expected_group)
#         if group_issue:
#             item_problems.append(group_issue)

#         permission_issue: str | None = check_permissions(item)
#         if permission_issue:
#             item_problems.append(permission_issue)

#         if item_problems:
#             problems[item] = item_problems

#     return problems
