# Plan: Address collectstatic failure and uv environment warning

## Summary of failure
- While running `lib_django_updater.run_collectstatic()` against the project at `.../site_checker_project_dj4p2`, the command failed:
  - Command: `uv run ./manage.py collectstatic --noinput --clear`
  - Return code: 1
  - Key error: `PermissionError: [Errno 13] Permission denied: '/tmp/AlTest1.out'`
  - uv warning: `VIRTUAL_ENV=...auto-updater-<id>` does not match project environment `.venv`; "use `--active` to target the active environment instead".

## Likely root cause(s)
- The `--clear` flag instructs Django to delete everything under `STATIC_ROOT` before collecting.
- The stack shows Django attempting to delete `/tmp/AlTest1.out`, which implies `settings.STATIC_ROOT == '/tmp'` (or otherwise resolves to `/tmp`). This is unsafe because `/tmp` is shared and may contain files owned by other processes or with restricted permissions.
- The uv warning is benign for functionality (uv selected the project `.venv`, which worked), but it is noisy and could confuse future debugging.

## Planned changes to the auto-updater (code changes to schedule separately)
1. Make `--clear` conditional and safe:
   - Before invoking `collectstatic`, query `STATIC_ROOT` via a quick Django command:
     - `uv run ./manage.py shell -c "from django.conf import settings; print(settings.STATIC_ROOT)"`.
   - Consider `--clear` only if `STATIC_ROOT` is a subdirectory of `project_path` and not a system dir (`/`, `/tmp`, `/var/tmp`, etc.).
   - If unsafe, log a warning and omit `--clear` for that run.
2. Improve logging for diagnostics:
   - Log resolved `STATIC_ROOT` and whether `--clear` was used.
   - On failure, include `settings.STATICFILES_STORAGE` and relevant staticfiles finders for context.

