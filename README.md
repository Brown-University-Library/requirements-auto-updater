## Overview...

Enables automatic self-updating! (To a limited extent.)

Called directly -- or, typically, by a cron job -- this script checks to see if a compile of the appropriate `requirements.in` file would create anything different from the previous run.

If so, it will update the venv, make it active, and notify the project admins.

_(Code is working and actively updating the `bdr_deposits_uploader` on dev.)_

---


## Flow...

(see `manage_update()`, near bottom dundermain, for details)

- determines the local/staging/production environment
- determines the python version
- determines the group
- determines a `uv` path
- determines the admin-emails
- compiles and saves appropriate requirements file
    - will create the `requirements_backups` directory in the "outer-stuff" directory if needed
- checks it to see if anything is new
- if so: 
    - updates the project's virtual-environment
    - makes the changes active
    - performs a diff showing the change
    - emails the diff to the project-admins
- updates permissions on the venv and the `requirements_backups` directory

---


## Usage...

- Directly:
    `$ uv run ./self_update.py "/path/to/project_code_dir/"`

- Via cron (eg to run every day at midnight) (all one line):
    `0 0 * * * cd "/path/to/self_updater_code/"; ../env/bin/uv run ./self_update.py "/path/to/project_code_dir/"`

---


## Project assumptions...

- All requirements files are in a top-level `requirements` directory.
- The requirements files are named `local.in`, `staging.in`, and `production.in` (it's ok to inherit from `base.in`).
- The requirements files contain tilde-notation (`package~=1.2.0`) wherever possible.
- The virtual environment is in the "outer-stuff" directory, sim-linked via an `env` file.
- There is a `.env` file in the "outer-stuff" directory.
- The `.env` file contains an `ADMINS_JSON` entry with the following structure:
    ```
    ADMINS_JSON='
        [
            [ "exampleFirst1 exampleLast1", "example1@domain.edu" ],
            [ "exampleFirst2 exampleLast2", "example2@domain.edu" ]
        ]'
    ```

---

## Notes...

- Assumes`uv` is accessible
    - Checks the `which uv` path. If nothing found, will then look for `uv` at `../env/bin/uv`. So add `uv` to the `requirements.in` file if uv isn't available via `which` on your server _(note that the venv does not need to be activated, it just exists to get `uv` on the servers)_
    - (We should get `uv` installed globally on all our servers. It's that good.)

- Suggestion: we do not tweak this script for different project-structures; rather, we restructure our apps to fit these assumptions (to keep this script simple).

- The `backup_requirements` dir defaults to storing the last 30 compiled requirements files. With a cron-job running once-a-day, that gives us a month to detect a problem and be able to access the previously-active `requirement.txt` file. You can tell which were active because they'll contain the string `# ACTIVE` at the top.

---


## Motivation...

We need to make upgrading dependency-packages more sustainable. 

By definition, the third part of package-notation (`major`, `minor`, `patch`) infers both backwards-compatibility and bug-fixes, so this seems like it should lighten the technical-debt load a bit.

---


## TODOs...

- ~~Create diff of changes~~
- ~~Email the diff to the admins.~~
- ~~Add tests for this script.~~
- Add the ability to run `$ python ./run_tests.py` on project.
- Explore shell-script version.

---
