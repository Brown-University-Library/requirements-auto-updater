# /// script
# requires-python = "==3.12.*"
# ///


import argparse
import grp
import os
import pathlib
import stat
import subprocess
import sys

EXPECTED_GROUP: str = os.environ['TEMP__EXPECTED_GROUP']


def check_group(item: pathlib.Path, expected_group: str) -> str | None:
    try:
        item_group: str = grp.getgrgid(item.stat().st_gid).gr_name
    except Exception as err:
        return f'Cannot determine group: {err}'

    if item_group != expected_group:
        return f'Incorrect group: expected {expected_group}, got {item_group}'
    return None


def check_permissions(item: pathlib.Path) -> str | None:
    try:
        st_mode: int = item.stat().st_mode
    except Exception as err:
        return f'Cannot stat: {err}'

    if not (st_mode & stat.S_IWGRP):
        return 'Not group-writeable'
    return None


def check_files(path: pathlib.Path, expected_group: str) -> dict[pathlib.Path, list[str]]:
    problems: dict[pathlib.Path, list[str]] = {}

    for item in path.rglob('*'):
        item_problems: list[str] = []

        group_issue: str | None = check_group(item, expected_group)
        if group_issue:
            item_problems.append(group_issue)

        permission_issue: str | None = check_permissions(item)
        if permission_issue:
            item_problems.append(permission_issue)

        if item_problems:
            problems[item] = item_problems

    return problems


def validate_arg() -> pathlib.Path:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description='Attempt to change group and verify permissions of files recursively.'
    )
    parser.add_argument('directory', type=pathlib.Path, help='Directory to process')
    args: argparse.Namespace = parser.parse_args()

    if not args.directory.exists() or not args.directory.is_dir():
        print(f'Error: {args.directory} is not a valid directory.')
        sys.exit(1)

    return args.directory


def main() -> None:
    directory: pathlib.Path = validate_arg()
    group: str = EXPECTED_GROUP

    try:
        subprocess.run(['chgrp', '-R', group, str(directory)], check=True)
    except subprocess.CalledProcessError as e:
        print(f'chgrp failed with error: {e}')

    problems: dict[pathlib.Path, list[str]] = check_files(directory, group)

    if not problems:
        print('All files have the correct group and are group-writeable.')
    else:
        print('Problems found:')
        for path, issues in problems.items():
            for issue in issues:
                print(f'{path}: {issue}')


if __name__ == '__main__':
    main()
