# Recent Prompts

_(for reference)_


## original prompt

› Goal: Add a getfacl check to the environmental scan.

  Context:

  - By far the most frequent blocker to this script running successfully -- is a failure of the environmental scan's check that all files in the target
  project-repo are group-writeable.

  - We have a code-update script that ensures that all files are left in a group-writeable state. But new files created during the normal execution of the
  webapp are sometimes not group-writeable.

  - The files flagged are usually `project/.venv` pycache files.

  - From research, I've found this command does what I want -- ensure that all new files are grouop read-writeable:

      ```
      find "$PROJECT_DIR_PATH" -type d -exec sudo setfacl -m d:g:"$GROUP":rwX,d:m::rwX {} +
      ```

  - I may end up adding this to the code-update-script, but for now want to add a check to the environmental scan to ensure that facls are set, because
  normal `ls` interaction with the server files doesn't indicate facl status.

  - example output showing facls _are_ set:

      ```
      $  getfacl ./SOME_PROJECT_DIR
      # file: SOME_PROJECT_DIR
      # owner: SOME_USER
      # group: THE_GROUP
      # flags: -s-
      user::rwx
      group::rwx
      other::r-x
      default:user::rwx
      default:group::rwx
      default:group:THE_GROUP:rwx
      default:mask::rwx
      default:other::r-x
      ```
  - example output showing facls are _not_ set:

      ```
      $  getfacl ./SOME_PROJECT_DIR
      # file: SOME_PROJECT_DIR
      # owner: SOME_USER
      # group: THE_GROUP
      # flags: -s-
      user::rwx
      group::rwx
      other::r-x
      ```

  Tasks:

  - Review `requirements-auto-updater/AGENTS.md` for code-directives to follow.

  - Make a PLAN to add a check to the environmental scan to ensure that facls are set.

  - Review `requirements-auto-updater/lib/lib_environment_checker.py` and it's caller and follow that pattern.

  - Include suggestions and a recommendation for where in the series of checks this should be placed.

  - I _think_ the check on the project-directory only should be sufficient, because our team has full-control over these servers, so there wouldn't be
  varied users implementing facls differently, and the setfacl command listed in the context should take are of all new files and directories. Evaluate this
  decision.

  - The check should use the `getfacl` command listed in the context for verification. Evaluate this approach.

  - If the facls are not set, the script should handle the error and subsequent notification in the way other environmental check failures are handled.

  - Save the plan to `requirements-auto-updater/PLAN__facl_environmental_check.md`.


## subsequent prompts

› I've made a few minor changes to the plan.

  Ignore the for-reference original prompt at bottom.

  Review the plan changes and update the plan -- and simplify decision-point decisions.

  Add to the plan a directive to review `requirements-auto-updater/AGENTS.md` before implementing any code changes.

  Add to the plan any useful contextual info that might be useful if implementation occurs in a different session.

---

- Review `requirements-auto-updater/AGENTS.md` for coding directives to follow.

- Review `requirements-auto-updater/PLAN__facl_environmental_check.md`.

- Implement the plan.

---
