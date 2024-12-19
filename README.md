## Overview...

Enables automatic self-updating! (To a limited extent.)

Called by a cron job, it checks to see if a requirements.in compile would create anything different from the previous run.

If so, it will activate the project's venv, and run `uv pip sync...' against the newly compiled file, auto-updating the venv.

_(Code is working an actively updating the `bdr_deposits_uploader` on dev.)_

---


## Flow...

(see `manage_update()`, near bottom dundermain, for details)

- determines the local/staging/production environment
- determines the python version
- determines the group
- compiles and saves appropriate requirements file
- checks it to see if anything is new
- if so, updates the project's virtual-environment

---


## Usage...

- Directly:
    `$ uv run ./self_update.py "/path/to/project_code_dir/"`

- Via cron (eg to run every day at midnight):
    `0 0 * * * /path/to/uv run /path/to/self_update.py "/path/to/project_code_dir/"`

---


## Project assumptions...

- All requirements files are in a top-level `requirements` directory.
- The requirements files are named `local.in`, `staging.in`, and `production.in`.
- The requirements files contain tilde-notation (x~=1.2.0) where possible.
- The virtual environment is in a parent-level `env` (simlink) directory.

---

## Notes...

- Assumes`uv` is accessible
    - Ideally `uv` will be installed globally, but for now this script-install will be able to reference `uv` at `../env/bin/uv` _(note that the venv does not need to be activated, it just exists to get `uv` on the servers)_
- Suggestion: we do not tweak this script for different project-structures; rather, we restructure our apps to fit these assumptions (to keep this script simple).
- The `backup_requirements` dir defaults to storing the last 30 compiled requirements files. With a cron-job running once-a-day, that gives us a month to detect a problem and be able to access the previously-active `requirement.txt` file. You can tell which were active because they'll contain the string `# ACTIVE` at the top.

---


## Motivation...

The need to make upgrading dependency-packages more sustainable. By definition, the third part of package-notation infers both backwards-compatibility and bug-fixes, so this seems like it should lighten the technical-debt load a bit.

---


## TODOs...

- Add tests.
- Email on error.
- Explore shell-script version.

---
