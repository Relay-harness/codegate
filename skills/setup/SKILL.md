---
name: setup
description: Set up CodeGate in the current repository. Creates codegate.toml from detected test/lint scripts, vendors .codegate/runner.py and installs Git pre-commit/pre-push hooks.
disable-model-invocation: true
---

# Set up CodeGate in this repository

In Codex, or anywhere `${CLAUDE_PLUGIN_ROOT}` is not expanded below, use `uvx --from git+https://github.com/Relay-harness/codegate.git codegate` in place of `"${CLAUDE_PLUGIN_ROOT}/scripts/codegate"`.

The plugin's Bash hook runs only in repositories with both `codegate.toml` and a local CodeGate install receipt. This setup creates that opt-in and adds Git hooks, so ordinary `git commit` and `git push` commands run the gate too.

1. Confirm you are at the root of a Git repository (`git rev-parse --show-toplevel`). Stop and tell the user if not.

2. Install the config, the vendored runner and the Git hooks:

   ```bash
   "${CLAUDE_PLUGIN_ROOT}/scripts/codegate" init --git
   ```

   Do not pass `--claude`. The plugin already provides the Claude hook, and a project-local copy would only duplicate it. If the command refuses because `core.hooksPath` is set (Husky, pre-commit and similar), run `init` without `--git` and show the user how to call `python3 .codegate/runner.py check --mode commit` from their hook manager.

3. Show the user the generated `codegate.toml`. If no checks were detected, ask which test command the project uses and add it as a `[[checks]]` entry. Shipping stays blocked until at least one check exists. Commands are argv arrays, not shell strings.

4. Run `"${CLAUDE_PLUGIN_ROOT}/scripts/codegate" doctor`. With the plugin, a `WARN Claude Bash hook installed` line is expected, because the hook comes from the plugin rather than `.claude/settings.local.json`.

5. Run `"${CLAUDE_PLUGIN_ROOT}/scripts/codegate" check` and report the result.

6. Tell the user to review and commit `codegate.toml` and `.codegate/runner.py`. Do not commit them yourself unless asked.
