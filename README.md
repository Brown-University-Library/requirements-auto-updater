[![CI tests](https://github.com/Brown-University-Library/requirements-auto-updater/actions/workflows/ci_tests.yaml/badge.svg?branch=main)](https://github.com/Brown-University-Library/requirements-auto-updater/actions/workflows/ci_tests.yaml)


## On this page...

- [Overview](#overview)
- [Flow](#flow)
- [Usage](#usage)
- [Project assumptions](#project-assumptions)
- [Notes](#notes)
- [Motivation](#motivation) 

---


## Overview...

Enables automatic requirements and venv updating.

Called directly -- or, typically, by a cron job -- this script:
- checks a bunch of expectations about the project
    - if expectations fail, an email noting the failure will go out to: 
        - the target-project admins if possible 
        - otherwise the auto-updater admins
- on `staging`, runs `uv sync --upgrade --group staging --dry-run --output-format json` to see whether a real update is needed before mutating the target repo.
    - if the dry run reports no changes, the script does nothing further.
    - if the dry run reports lockfile-only metadata churn (currently the `exclude-newer` case), the script does nothing further.
    - if the dry run reports a substantive dependency change, the script performs the real update, then re-runs the project's tests, runs django's `collectstatic` if necessary, and notifies the project-admins.
- on `production`, skips upgrade discovery entirely and runs `uv sync --locked --group prod` so the deployed `.venv` matches the already-committed `uv.lock`.

---


## Flow...

(see the `auto_updater.py manage_update() function`, for details)

- Performs these initial checks:
    - validates submitted project-path
    - determines the admin-emails
    - validates expected branch
    - validates expected git-status
    - ensures a python version is listed
    - ensures `pyproject.toml` includes a `[tool.uv] exclude-newer` setting
    - determines the local/staging/production environment
    - validates the `uv` path
    - determines the group
    - validates group and permissions on the venv and the `requirements_backups` directories
    - runs project's `run_tests.py`
- If any of the above steps fail, emails project-admins (or updater-admins)
- On `staging`:
    - runs `uv sync --upgrade --group staging --dry-run --output-format json`
    - if the dry run reports no changes, stops without backing up `uv.lock` or updating `.venv`
    - if the dry run reports lockfile-only metadata churn, stops without backing up `uv.lock` or updating `.venv`
    - if the dry run reports a substantive change:
        - saves a backup of `uv.lock` to `../uv.lock.bak`
        - runs the real `uv sync --upgrade --group staging`
        - evaluates whether `uv.lock` actually changed
        - runs project's `run_tests.py`
            - on test success
                - performs a diff on new and old `uv.lock` showing the change, and creates diff text
                - if a django app
                    - runs its `collectstatic` command
                    - runs the usual `touch` command to let passenger know to reload the django-app
                - runs a git-pull, then a git-add, then a git-commit, then a git-push
                - emails the diff (and any issues) to the project-admins
            - on test failure
                - restores original `uv.lock`
                - runs `uv sync --frozen --group staging`
                - runs project's `run_tests.py` again
                - emails the canceled-diff (and test-failures) to the project-admins
- On `production`:
    - skips upgrade discovery entirely
    - runs `uv sync --locked --group prod`
    - does not back up or diff `uv.lock`
    - does not run git commit/push operations
    - skips tests as before
    - still runs django `collectstatic` and restart handling if the installed django version changed across the locked sync
- Finally, attempts to update group & permissions on the venv and the `requirements_backups` directories


## Usage...

- Directly:
    ```
    $ cd "/path/to/requirements-auto-updater/"
    $ uv run --env-file "../.env" ./auto_updater.py --project "/path/to/project_to_update_code_dir/"
    ```

- Via cron on servers (eg to run every day at 12:01am) (all one line):
    ```
    1 0 * * * PATH=/usr/local/bin:$PATH cd "/path/to/requirements-auto-updater/" && /path/to/uv run --env-file "../.env" ./auto_updater.py --project "/path/to/project_to_update_code_dir/"
    ```

---


## Project assumptions...

- A `pyproject.toml` file exists, with a `dependencies = []` entry, a `[dependency-groups]` entry with `staging` and `prod` entries, and a `[tool.uv]` section with an `exclude-newer` setting (for example, `"2 days"`).
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

- The `exclude-newer` setting reduces the chance of pulling a newly published poisoned registry package. The specific value can vary by project.

- To monitor: using the tilde-notation to ensure that only the `patch` version is updated _could_ still install new non-patch-level versions of dependencies. In the many months of monitoring this in real usage on three projects, this has not caused an issue.

---


## Motivation...

We need to make upgrading dependency-packages more sustainable. 

By definition, the third part of package-notation (`major`, `minor`, `patch`) infers both backwards-compatibility and bug-fixes, so this should lighten the technical-debt load. However it _is_ possible for `patch` upgrades to contain backwards-incompatibilites -- [example](https://www.djangoproject.com/weblog/2023/may/03/security-releases/).

---
