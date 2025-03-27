## Overview...

Enables automatic requirements and venv updating --to a limited extent.

Called directly -- or, typically, by a cron job -- this script:
- checks a bunch of expectations about the project
    - if expectations fail, an email noting the failure will go out to the target-project admins if possible; otherwise the auto-updater admins.
- checks to see if a re-compile of the appropriate `requirements.in` file would create anything different from the previous run.
    - if the recompile is different from the previous day's, it will update the venv, make it active, re-run tests, run django's `collectstatic` if necessary, and notify the project-admins.

_(Code is working and actively updating the `bdr_deposits_uploader` (dev) and `sitechecker` (dev & prod), and `bdr_storage` (dev).)_

---


## Flow...

(see `manage_update()`, near bottom dundermain, for details)

- Performs these initial checks:
    - validates submitted project-path
    - determines the admin-emails
    - validates expected branch
    - validates expected git-status
    - determines the python version
    - determines the local/staging/production environment
    - determines a `uv` path
    - determines the group
    - validates group and permissions on the venv and the `requirements_backups` directories
    - calls project's run_tests.py (on local and dev-servers)

- If any of the above steps fail, emails project-admins (or updater-admins)

- Compiles and saves appropriate requirements file
    - creates the `requirements_backups` directory in the "outer-stuff" directory if needed
    - saves the last 30 backups
    - note that because the compile is to a "new" file (that's date-stamped), this ensures the latest patch is actually in the newly-compiled `.in` file. This thus avoids the situation we've seen, with both `pip` and `uv`, where an existing `.in` file can prevent the latest patch from being defined in the newly-compiled file.

- Checks it to see if anything is new

- If there is something new: 
    - updates the project's virtual-environment
        - normally a venv has to be made "active", by being sourced, before the venv can be updated from the compiled `.txt' file. [This explanation](https://github.com/Brown-University-Library/requirements-auto-updater/blob/6e8b540ad1a6f389e115f2cfb364751380b94f58/auto_updater.py#L128-L136) describes how the venv is updated programmatically.
    - runs the usual `touch` command to let passenger know to reload the django-app
    - performs a diff showing the change, and creates diff text
    - checks the diff for a django update, and if django was updated, runs its collectstatic command
    - saves the updated `.txt` file and runs a git-pull, then a git-add, then a git-commit, then a git-push
    - calls project's run_tests.py again (on local and dev servers)
    - emails the diff (and any test-issues) to the project-admins

- Finally, attempts to update group & permissions on the venv and the `requirements_backups` directories

---


## Usage...

- Directly:
    ```
    $ cd "/path/to/requirements-auto-updater/"
    $ uv run ./auto_update.py "/path/to/project_to_update_code_dir/"
    ```

- Via cron on servers (eg to run every day at midnight) (all one line):
    ```
    0 0 * * * PATH=/usr/local/bin:$PATH cd "/path/to/requirements-auto-updater/" && uv run ./auto_updater.py "/path/to/project_to_update_code_dir/"
    ```

---


## Project assumptions...

- All requirements files are in a top-level `requirements` directory.
- The requirements files are named `local.in`, `staging.in`, and `production.in` (it's ok to inherit from `base.in`).
- The requirements files contain tilde-notation (`package~=1.2.0`) wherever possible. That third numeral is important; we only want to update the `patch` version.
- The virtual environment is in the "outer-stuff" directory, sim-linked via an `env` file.
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

- The `backup_requirements` dir defaults to storing the last 30 compiled requirements files. With a cron-job running once-a-day, that gives us a month to detect a problem and be able to access the previously-active `requirement.txt` file. You can tell which were active because they'll contain the string `# ACTIVE` at the top.

- We've seen that `pip` and `uv` compilation, from `.in` to `.txt` files, may not actually compile a desired newer package-version if the existing `.txt` output path already exists. This auto-updater avoids that by compiling to the `backup_requirements` dir with a date-stamped filename. (Then a comparison with the previous backup occurs.)

- To monitor: using the tilde-notation to ensure that only the `patch` version is updated _could_ still install new non-patch-level versions of dependencies. In the 2 months of monitoring this in real usage on two projects, this has not caused an issue.

---


## Motivation...

We need to make upgrading dependency-packages more sustainable. 

By definition, the third part of package-notation (`major`, `minor`, `patch`) infers both backwards-compatibility and bug-fixes, so this should lighten the technical-debt load. However it _is_ possible for `patch` upgrades to contain backwards-incompatibilites -- [example](https://www.djangoproject.com/weblog/2023/may/03/security-releases/).

---
