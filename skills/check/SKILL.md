---
name: check
description: Run CodeGate's quality gate (the checks in codegate.toml) for the current repository, then fix whatever it reports. Use before committing, pushing or opening a pull request, or when a CodeGate hook blocked one.
---

# Run the CodeGate check

1. From the repository root, run the gate:

   ```bash
   "${CLAUDE_PLUGIN_ROOT}/scripts/codegate" check
   ```

   If that path is not expanded in your client, use the vendored runner instead: `python3 .codegate/runner.py check`.

2. If it reports `PASS`, say so and continue with what you were doing.

3. If it reports `BLOCKED`, read each failed check's output, fix the root cause in the code, and run the check again. Repeat until it passes or you need a decision from the user.

Never get past the gate by weakening it: do not edit `codegate.toml` or tests to make failures disappear, do not use `git commit --no-verify` or `git push --no-verify`, and do not run shipping commands through `cd`, `git -C` or wrapper scripts. If a check looks wrong or flaky, explain why and ask the user.

If there is no `codegate.toml`, or it exists but `.git/codegate/install.json` does not, the repository has not been set up on this machine. Suggest `/codegate:setup` instead.
