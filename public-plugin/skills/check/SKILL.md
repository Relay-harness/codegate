---
name: check
description: Run CodeGate quality checks for an accessible local Git repository and explain or fix failures. Use before committing or pushing, or after a Git hook blocks an operation.
---

# Check the repository

Resolve the target Git repository to an absolute path. If no accessible local checkout is available, ask for one; do not invent a path.

Prefer the `codegate_check` MCP tool with that absolute `path`. If the tool is unavailable after setup, run `python3 .codegate/runner.py --repo "/absolute/repository" check` from the target repository, using a Python 3.11+ interpreter.

Report PASS only when supported by the current result. Explain BLOCKED output, fix the underlying code within the user's task, and rerun. Do not weaken checks or tests, bypass Git hooks, or interpret a pass as shipping authorization.

If codegate.toml is missing, explain that checks have not run and offer the setup skill. This directory edition does not install agent lifecycle hooks. Git hooks require per-repository setup; required CI is needed to enforce checks against deliberate local bypass.
