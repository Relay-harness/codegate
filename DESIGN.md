# Design and boundaries

## Implementation

One importable/standalone Python module; no runtime dependencies.

- `config`: validated, fail-closed TOML policy. Unknown fields and empty commands fail.
- `snapshot`: HEAD identity, Git index entries, content hashes of nonignored tracked/untracked regular files, symlink text and policy bytes. Reject tracked directories/submodules. Ignored/external state remains outside the snapshot.
- `builtin_checks`: conflict/whitespace checks plus bounded Python syntax and narrow credential patterns.
- `run_command`: direct argv subprocess in the repository, no implicit shell, no interactive stdin, CI=1, bounded time/output, POSIX process-group teardown.
- `check`: run built-ins and configured checks; reject changed inputs; persist a local diagnostic report. No success cache.
- `claude_hook`: documented PreToolUse JSON denial contract. Pattern detection is intentionally best-effort; it preserves normal permissions on success. Optional Stop feedback avoids repeated blocking loops.
- `git_hook`: stage/cleanliness rules, validate HEAD-only push refs, run checks, chain prior executable hooks with original arguments and push stdin.
- `plugin_hook`: entry point for the Claude Code/Codex plugin hook. It resolves the repository from the payload `cwd` and passes through unless the checkout opted in (`codegate.toml` plus a local install receipt, so a cloned policy alone runs nothing) and no project-local Claude hook is installed. Errors before opt-in pass through; after opt-in, the `claude_hook` deny contract applies.
- `install/uninstall`: local settings merge, per-repo receipts/backups, unchanged-wrapper verification before restoration, no global Git configuration.
- `mcp_server`: synchronous newline JSON-RPC MCP 2024-11-05 tool server. The repository is resolved on each call, from an optional absolute `path` argument (required with `--require-path`). A tool result is advisory, not authorization.

## Why not Harbor or a second LLM?

The common developer path should not require a benchmark harness, containers, provider credentials or model costs. Deterministic project checks are the starting enforcement signal. A team can add a Harbor sandbox evaluation as one explicit command when it has suitable task fixtures; doing so is opt-in and carries its own runtime/cost requirements.

## Trust model

Trusted developer, reviewed project configuration, ordinary AI-assisted workflow. The model/user is not treated as an adversary with unrestricted host permissions: such an actor can remove local hooks, alter policy/tests, use another tool or bypass Git hooks. Use mandatory trusted CI/branch protections for stronger merge control.

Project tests run as the host user. They are arbitrary code. Process-group cleanup is a best-effort bound, not an OS sandbox: malicious descendants can detach. External state, ignored dependencies and changes after checking are not sealed. PASS means the declared checks passed on the observed working state, not proof of safety, completeness or bug freedom.

## Deliberate v0.1 limits

macOS/Linux only. No automatic installation into existing user repositories. No global hook manager replacement. No linked-worktree Git-hook installation, submodule coverage, non-HEAD/tag-object push support, live client certification, ChatGPT web control, adversarial shell parsing or universal deployment interception. No claimed hosted enforcement service.
