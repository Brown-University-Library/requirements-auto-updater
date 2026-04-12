# Idea Assessment

## Prompt

Goal: don't perform `--upgrade` sync on prod.

Context:

- The whole purpose of this script is to auto-update packages in a way that is useful and safe.

- The "safe" part currently is implemented by ensuring tests still pass (on dev), and incorporating a rollback if necessary. And via a `uv --exclude-newer "2 days" delay (not in this code, but in the target project's `pyproject.toml`). And via the target project's `pyproject.toml` only targeting third-digit "patch" package upgrades.

- I have an additional idea I want to incorporate. In our code-update scripts, we never include the `--upgrade` flag on the uv sync command -- the command we use in those code-update scripts is:

```
uv sync --locked --group $UV_GROUP
```

...the philosophy being that we want to assume that production is only updated from a fixed uv.lock file that has already been tested.

So -- the idea: detect if the script is running on prod, and if it is, don't use the `--upgrade` flag when running uv sync.

Tasks:

- Review the existing code-flow.

- Review the dev/prod analysis at `requirements-auto-updater/DEV_VS_PROD.md`.

- Review `requirements-auto-updater/AGENTS.md` for code-directives to follow.

- Give me an assessment of this change -- don't change any code at this point. Save the assessment to `requirements-auto-updater/IDEA_ASSESSMENT.md`, with this prompt near the beginning of the file.


## Short assessment

This is a good idea in principle, but only if the production path is treated as a deployment/synchronization path rather than as an update-discovery path.

Right now the script has one unified mental model for both dev and prod:

1. run `uv sync --upgrade --dry-run --output-format json`
2. decide whether there is a substantive dependency change
3. if yes, run a real `uv sync --upgrade`
4. diff `uv.lock`
5. optionally test, rollback, commit, push, and email

That model fits dev/staging reasonably well. It does not fit the philosophy of "prod should only realize an already-tested lockfile".

## Why the idea makes sense

The current dev/prod split already makes production the less safe path:

- production skips initial tests
- production skips follow-up tests
- production skips rollback verification tests
- production still performs the real sync step

See:

- `requirements-auto-updater/DEV_VS_PROD.md`
- `requirements-auto-updater/lib/lib_call_runtests.py:25`
- `requirements-auto-updater/lib/lib_uv_updater.py:49`

So removing `--upgrade` from the production sync step is directionally correct. It would reduce the chance that production resolves a newer dependency set that was never exercised on dev/staging first.

That is consistent with the operational rule:

- dev/staging may discover and validate dependency upgrades
- production should consume a committed, already-tested `uv.lock`

## The main design issue

A narrow change to only the production "real sync" command would leave the current flow internally inconsistent.

Today:

- dry-run uses `--upgrade`
- real sync uses `--upgrade`

If production changes to:

- dry-run still uses `--upgrade`
- real sync uses no `--upgrade`

then the script may do this:

1. production dry-run reports a substantive upgrade is available
2. production enters the update path
3. production runs a non-upgrade sync against the existing committed `uv.lock`
4. `uv.lock` likely does not change
5. the script sees no diff and skips downstream work

That would not be catastrophic, but it would mean the dry-run signal no longer matches the action that follows.

The mismatch comes from the current code structure:

- `manage_update()` decides whether work is needed based on `inspect_pending_sync()` in `requirements-auto-updater/auto_updater.py:138`
- `inspect_pending_sync()` always builds its dry-run command with `--upgrade` in `requirements-auto-updater/lib/lib_uv_updater.py:138`
- `manage_sync()` always performs a real `--upgrade` sync in `requirements-auto-updater/lib/lib_uv_updater.py:61`

Those three pieces currently assume the same meaning of "pending change".

## What this probably means operationally

If the intended production behavior is:

- "take the lockfile that is already in git and make `.venv` match it"

then production should probably not participate in upgrade detection at all.

That means the production path should likely be conceptually closer to:

```bash
uv sync --locked --group prod
```

or possibly:

```bash
uv sync --frozen --group prod
```

depending on whether the project wants to allow lockfile regeneration checks versus strict lockfile realization only.

In that model, production is no longer trying to answer:

- "is there a newer patch release available?"

It is answering:

- "does this machine's environment match the committed lockfile?"

Those are different jobs.

## Recommendation

I would recommend this change, but not as a one-line flag tweak.

I would recommend making the workflow explicit:

- `staging` remains the environment that performs upgrade discovery
- `staging` remains the environment that tests upgraded dependencies
- `staging` remains the environment that mutates `uv.lock`, commits, and pushes when safe
- `production` becomes a lockfile-consumer only

If you adopt that model, then the production path should probably:

- not use `--upgrade` for the real sync
- probably not use `--upgrade` for the dry-run either
- probably not classify "substantive dependency change available upstream" on production
- probably focus on syncing `.venv` to the committed `uv.lock`

## Likely code consequences if this idea is implemented well

The clean implementation likely requires more than changing one command-builder.

Areas that would need review:

- `requirements-auto-updater/lib/lib_uv_updater.py`
  - the sync command builder currently assumes one command shape for all environments
  - the dry-run command builder currently assumes upgrade-discovery semantics
- `requirements-auto-updater/auto_updater.py`
  - the top-level flow currently assumes dry-run classification decides whether to do a real sync
  - that assumption may no longer be valid for production
- tests
  - current tests cover production skipping rollback tests, but not a distinct "locked prod sync" flow

## Practical options

There are two plausible implementation directions.

### Option A: Minimal change

Change only the production real sync so it does not use `--upgrade`.

Assessment:

- low implementation cost
- partially aligns prod with the desired philosophy
- leaves dry-run semantics inconsistent on prod
- likely produces some "dry-run said update exists, but nothing changed" runs

This is acceptable only if you are comfortable with that inconsistency.

### Option B: Clean separation

Treat production as a different workflow, not just a different flag.

Assessment:

- better matches the stated operational philosophy
- easier to reason about
- safer long-term
- requires a somewhat larger refactor and new tests

This is the stronger design.

## Additional concern noticed during review

There is an existing production-related inconsistency in the rollback code inside `manage_update()`.

This line builds:

```bash
uv sync --frozen --group production
```

because it uses `environment_type` directly:

- `requirements-auto-updater/auto_updater.py:180`

But elsewhere the code maps `production` to the dependency group name `prod`:

- `requirements-auto-updater/lib/lib_uv_updater.py:159`

So if that rollback branch were ever exercised on production, the group name would not match the established mapping.

That is separate from your idea, but it is worth keeping in mind when changing the prod path.

## Bottom line

The idea is sound.

If your real intent is "production must never resolve a newer dependency set on its own", then production should stop being an upgrade environment and should become a lockfile-realization environment.

So my assessment is:

- yes, this is a worthwhile change
- no, it should not be implemented as only "remove `--upgrade` from one prod sync call" unless you accept a somewhat awkward flow
- the cleaner solution is to split staging update-discovery from production lockfile-consumption more explicitly
