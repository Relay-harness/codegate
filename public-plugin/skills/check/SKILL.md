---
name: check
description: Run CodeGate quality checks for a local Git repository and explain or fix failures. Use before committing or pushing, or after a repository Git hook blocks an operation.
---

# Check the repository

1. Resolve the intended Git repository to an absolute path. If the local checkout or command execution is unavailable, explain the desktop requirement and ask for an accessible local thread; do not invent a path or result.
2. Resolve the bundled launcher from this skill's directory at `../../scripts/codegate`. Use its actual absolute path. Confirm Python 3.11+ and Git are available.
3. Read codegate.toml and explain the configured project commands before executing them. Run only checks within the user's authorized task. If the configuration is missing, explain that checks have not run and offer the setup skill.
4. Run `sh "/absolute/plugin/scripts/codegate" --repo "/absolute/repository" check`. The arguments are distinct argv values; preserve spaces in paths. These commands execute project code with the user's permissions, not in a sandbox.
5. Report PASS only from the current successful result. Explain BLOCKED output, fix the underlying code within the requested task, and rerun. Do not weaken checks or tests, bypass Git hooks, or treat PASS as permission to commit, push or deploy.

This public edition uses the bundled CLI directly and has no MCP tool. Repository Git hooks require explicit setup. Required CI is needed for enforcement against deliberate local bypass.
