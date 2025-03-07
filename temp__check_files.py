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
from typing import Any

EXPECTED_GROUP: str = os.environ['TEMP__EXPECTED_GROUP']


def check_permissions(path: pathlib.Path, expected_group: str) -> bool:
    """Recursively checks that each file/directory has the expected group and is group-writeable."""
    all_ok: bool = True
    for item in path.rglob('*'):
        try:
            st: os.stat_result = item.stat()
        except Exception as err:
            print(f'Cannot stat {item}: {err}')
            all_ok = False
            continue
        try:
            item_group: str = grp.getgrgid(st.st_gid).gr_name
        except KeyError:
            print(f'Group for {item} not found for gid {st.st_gid}')
            all_ok = False
            continue
        if item_group != expected_group:
            print(f'Group mismatch for {item}: found {item_group} (expected {expected_group})')
            all_ok = False
        if not (st.st_mode & stat.S_IWGRP):
            print(f'Permission error for {item}: not group-writeable')
            all_ok = False
    return all_ok


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description='Attempt to change group and verify permissions of files recursively.'
    )
    parser.add_argument('directory', type=str, help='Path to the directory to check')
    args: Any = parser.parse_args()

    pth: pathlib.Path = pathlib.Path(args.directory)
    if not pth.exists() or not pth.is_dir():
        print(f'Error: {pth} is not a valid directory.')
        sys.exit(1)

    group: str = EXPECTED_GROUP

    try:
        subprocess.run(['chgrp', '-R', group, str(pth)], check=True)
    except subprocess.CalledProcessError as e:
        print(f'chgrp failed with error: {e}. Running verification...')

    if check_permissions(pth, group):
        print('All files have the correct group and are group-writeable.')
    else:
        print('Some files do not have the correct group or permissions.')


if __name__ == '__main__':
    main()
