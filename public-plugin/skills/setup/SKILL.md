---
name: setup
description: Set up CodeGate in a local Git repository when the user requests it. Detect test and lint commands, vendor the runner, and install per-repository Git pre-commit and pre-push hooks.
---

# Set up the repository

1. Resolve the intended repository with `git rev-parse --show-toplevel`. Use an absolute repository path and confirm Python 3.11+ and Git are available. Stop if the local checkout cannot be accessed.
2. Read existing codegate.toml, package scripts, and hook-manager configuration. Explain the detected commands and review them before executing project code. Do not overwrite an existing policy or hook manager.
3. Resolve the bundled `scripts/codegate` launcher from this skill's location: it is at `../../scripts/codegate` relative to this SKILL.md directory. Use its absolute path. Run `sh "/absolute/plugin/scripts/codegate" --repo "/absolute/repository" init --git`.
4. If core.hooksPath is managed by Husky or another manager, use `init` without `--git`, then explain how to call `python3 .codegate/runner.py check --mode commit` and `--mode push` from the existing manager. Do not replace its settings.
5. Show generated codegate.toml. If no checks were found, ask for the project's actual test command and add an argv-array check. Do not report success with an empty policy. Run the gate only after the project commands have been reviewed.
6. Run the bundled launcher's `doctor` and `check` actions for the target repository. In this edition, a missing Claude Bash hook is expected: no agent lifecycle hook is bundled. Verify the requested Git hooks and report the actual quality-check result.
7. Ask the user to review codegate.toml and .codegate/runner.py for committing, unless a commit was already requested. Installation does not itself commit, push, deploy, or authorize shipping.
