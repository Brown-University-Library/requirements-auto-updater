## On this page...

- [Overview](#overview)
- [Flow](#flow)
- [Usage](#usage)
- [Project assumptions](#project-assumptions)
- [Notes](#notes)
- [Motivation](#motivation) 

---


## Overview...

Enables automatic requirements and venv updating --to a limited extent.

Called directly -- or, typically, by a cron job -- this script:
- checks a bunch of expectations about the project
    - if expectations fail, an email noting the failure will go out to the target-project admins if possible; otherwise the auto-updater admins.
- checks to see if a re-compile of the appropriate `requirements.in` file would create anything different from the previous run.
    - if the recompile is different from the previous day's, it will update the venv, make it active, re-run tests, run django's `collectstatic` if necessary, and notify the project-admins.

---


## Flow...

(see the `auto_updater.py manage_update() function`, for details)

- Performs these initial checks:
    - validates submitted project-path
    - determines the admin-emails
    - validates expected branch
    - validates expected git-status
    - ~determines the python version~
    - determines the local/staging/production environment
    - validates the `uv` path
    - determines the group
    - validates group and permissions on the venv and the `requirements_backups` directories
    - runs project's `run_tests.py`
- If any of the above steps fail, emails project-admins (or updater-admins)
- Saves a backup of `uv.lock` to `../uv.lock_backup`
- Runs `uv sync --upgrade --group staging` (for dev) or `uv sync --upgrade --group production` (for prod)
- Evaluates if `uv.lock` has changed
- If `uv.lock` has changed:
    - runs project's `run_tests.py`
        - on test success
            - runs `uv pip compile ./pyproject.toml -o ./requirements.txt`
            - performs a diff on new and old `uv.lock` showing the change, and creates diff text 
            - if a django app
                - runs its `collectstatic` command
                - runs the usual `touch` command to let passenger know to reload the django-app
            - runs a git-pull, then a git-add, then a git-commit, then a git-push
            - emails the diff (and any issues) to the project-admins
        - on test failure
            - restores original `uv.lock`
            - runs `uv sync --frozen`  # just updates the `.venv` from the `uv.lock` file
            - runs project's `run_tests.py` again
            - emails the canceled-diff (and test-failures) to the project-admins
- Finally, attempts to update group & permissions on the venv and the `requirements_backups` directories


## Usage...

- Directly:
    ```
    $ cd "/path/to/requirements-auto-updater/"
    $ uv run --env-file "../.env" ./auto_updater.py --project "/path/to/project_to_update_code_dir/"
    ```

- Via cron on servers (eg to run every day at 12:01am) (all one line):
    ```
    1 0 * * * PATH=/usr/local/bin:$PATH cd "/path/to/requirements-auto-updater/" && uv run --env-file "../.env" ./auto_updater.py --project "/path/to/project_to_update_code_dir/"
    ```

---


## Project assumptions...

- A `pyproject.toml` file exists, with a `dependencies = []` entry, and a `[dependency-groups]` entry, with `staging` and `prod` entries.
- The dependencies use tilde-notation (`package~=1.2.0`) wherever possible. That third numeral is important; we only want to update the `patch` version.
- There is a `.env` file in the "outer-stuff" directory.
- The `.env` file contains an `ADMINS_JSON` entry with the following structure:
    ```
    ADMINS_JSON='
        [
            [ "exampleFirstname1 exampleLastname1", "example1@domain.edu" ],
            [ "exampleFirstname2 exampleLastname2", "example2@domain.edu" ]
        ]'
    ```

---


## Notes...

- Assumes`uv` is accessible
    - Checks the `which uv` path. If nothing found, will raise an exception and email the project-admins. This is the reason for updating `PATH` in the cron-call.

- Suggestion: we do not tweak this script for different project-structures; rather, we restructure our apps to fit these assumptions (to keep this script simple, and for the benefits of a more standardized project structure).

- To monitor: using the tilde-notation to ensure that only the `patch` version is updated _could_ still install new non-patch-level versions of dependencies. In the 2 months of monitoring this in real usage on two projects, this has not caused an issue.

---


## Motivation...

We need to make upgrading dependency-packages more sustainable. 

By definition, the third part of package-notation (`major`, `minor`, `patch`) infers both backwards-compatibility and bug-fixes, so this should lighten the technical-debt load. However it _is_ possible for `patch` upgrades to contain backwards-incompatibilites -- [example](https://www.djangoproject.com/weblog/2023/may/03/security-releases/).

---
