# CodeGate

**Let AI write code. Make your checks approve shipping.**

A local quality gate for Claude Code, Codex and ordinary Git workflows. Python 3.11+, macOS/Linux, no runtime dependencies. This is a v0.1 open-source project. It ships as a Claude Code plugin, a Codex plugin (installable from the ChatGPT desktop app) and a plain CLI. Landing page: [`docs/index.html`](docs/index.html).

```text
Claude Code proposes commit/push
              ↓
       Claude PreToolUse hook
              ↓
  Syntax + obvious secrets + your tests/lint/types
              ↓
        PASS → normal permission flow
        FAIL → block + explain what to fix
              ↓
   Git pre-commit / pre-push check again
```

It does **not** prove code is bug-free, understand every business requirement, or replace code review. It enforces the checks your project defines. It does not need Harbor, REA, an API key, or a second model.

## Plugins

This repository is also a plugin marketplace for Claude Code and for Codex. Both plugins bundle the same pieces:

- a `PreToolUse` Bash hook (`hooks/hooks.json`) that gates shipping commands,
- the `codegate_check` MCP tool,
- `check` and `setup` skills (`skills/`).

Plugins load in every project. The plugin hook (`codegate hook plugin`) therefore does nothing unless the current checkout has opted in. That takes a `codegate.toml` plus a local install receipt in `.git/codegate/`, written by `init`/`install` (or `/codegate:setup`) on your machine. A cloned repository that only ships a `codegate.toml` cannot make the plugin run its commands. Teammates opt in with `python3 .codegate/runner.py install --git`. It also steps aside where a project-local `codegate install --claude` hook already exists, so checks never run twice. Unlike the project-local hook, the plugin hook does not set `onFailure: block`. If Python 3.11+ is missing, it fails open rather than blocking every Bash call in every project. Git hooks and CI remain the enforcement layers.

### Claude Code

```text
/plugin marketplace add Relay-harness/codegate
/plugin install codegate@codegate
```

Then, in the repository you want to protect, run `/codegate:setup`. It runs `init --git`: it writes `codegate.toml`, vendors `.codegate/runner.py` and installs Git hooks. It skips `--claude`, because the plugin provides that hook. Use `/codegate:check` to run the gate on demand. After setup, `codegate doctor` reports `WARN Claude Bash hook installed`. That is expected when the hook comes from the plugin.

### Codex and the ChatGPT desktop app

```bash
codex plugin marketplace add Relay-harness/codegate
```

1. Restart the ChatGPT desktop app, open the Plugins directory and install `codegate`.
2. Review and trust its hook with `/hooks`. Codex does not run plugin hooks until they are trusted.
3. Opt a repository in with `uvx --from git+https://github.com/Relay-harness/codegate.git codegate init --git`, or ask Codex to use the `setup` skill.

The Codex manifest is `.codex-plugin/plugin.json` and the marketplace is `.agents/plugins/marketplace.json`. Codex starts plugin MCP servers from the plugin directory, not from your project. Its MCP config therefore runs the server with `--require-path`, and `codegate_check` must be given the repository's absolute `path`.

This works in local Codex threads only. The ChatGPT web app cannot reach your files or run your tests, so CodeGate cannot gate code written there. Use Git hooks and required CI for that code.

## Quick start

Install the local project once:

```bash
uv tool install git+https://github.com/Relay-harness/codegate.git
```

Then, **from the repository you want to protect**:

```bash
codegate init --claude --git
codegate doctor
codegate check
```

Review `codegate.toml`, then commit `.codegate/runner.py` and `codegate.toml`. Restart Claude Code or reload its hooks and verify with `/hooks` before relying on the integration. The installer writes project-local `.claude/settings.local.json`, not global Claude settings. Claude may ask you to trust new project hook settings.

Node repositories: detect declared `lint`, `typecheck`, `test` and `build` scripts, and select npm/pnpm/yarn/bun from lockfiles. Python repositories with pyproject/pytest.ini plus tests: detect a pytest command and use the project's `.venv/bin/python` when available. Detection is a starting policy, not proof that these scripts test the right things. Test frameworks must already be installed in the project environment. `CI=1` is set to discourage interactive/watch behavior.

**No check commands detected? Shipping stays blocked.** Add your actual test command before continuing. No silent success on an empty policy.

### Teammate setup without installing a package

After the runner/config are committed, a teammate can use:

```bash
python3 .codegate/runner.py install --claude --git
python3 .codegate/runner.py doctor
python3 .codegate/runner.py check
```

The runner is self-contained. Each developer installs their own local hooks. Installing CodeGate does not install project dependencies, change global Git settings, or create commits/pushes for you.

## Configuration

For a Python unittest project:

```toml
version = 1
timeout = 300
secret_scan = true
python_syntax = true
ship_commands = ["npm publish", "vercel --prod"]

[[checks]]
name = "unit tests"
command = ["python3", "-m", "unittest", "discover", "-s", "tests"]
timeout = 120
```

Use the project's Python executable if its tests need a virtual environment, for example `.venv/bin/python`. Syntax inspection uses the Python running CodeGate; match that version to your source syntax or disable the built-in syntax scan and configure your own project-runtime syntax/type check.

For a Node project:

```toml
version = 1
timeout = 300

[[checks]]
name = "lint"
command = ["npm", "run", "lint"]
timeout = 60

[[checks]]
name = "types"
command = ["npm", "run", "typecheck"]
timeout = 60

[[checks]]
name = "tests"
command = ["npm", "run", "test"]
timeout = 120
```

Commands are arrays, executed directly without an implicit shell. For complex pipelines, commit a reviewed project script and call that script. Commands run sequentially and stop after the first failure. Each command has a deadline; the total budget is also capped at 600 seconds. A command exceeding 1 MB output is stopped and fails the gate. The last 12 KB is retained for diagnosis. Common detected token patterns are redacted; arbitrary secrets in test logs are not guaranteed to be removed.

There is no AI reviewer by default. Add your established security scanners, type checker, migration checks, contract tests, accessibility tests, or a sandbox evaluation as explicit commands. Tests can be expensive, destructive or networked: CodeGate runs them with **your user permissions and inherited environment**. Review configuration before trusting it. It is not a sandbox.

## What it blocks

### Claude Code

Use **Claude Code 2.1.295 or later** for the installed `onFailure: block` setting. This blocks the matched tool if the hook crashes, cannot start, or times out. Older Claude versions must not be treated as fail-closed; keep the independent Git/CI gates. A missing interpreter can block all matched Bash calls on supported versions; repair/remove the hook from a normal terminal if needed.

The `PreToolUse` Bash hook detects ordinary `git commit`, `git push`, `gh pr create`, `gh pr merge`, plus configured `ship_commands`. On failure it returns the documented `permissionDecision: deny` with a repair message. On success it returns no permission decision, so it does not auto-approve an action Claude would otherwise need permission for.

This is a convenience shell-pattern detector, **not** a complete Bash parser or security boundary. Aliases, wrapper scripts, other tools, encoded shell commands, subprocesses and alternate Git configurations can bypass it. Git hooks provide a second check for normal Git calls. The guard rejects shipping commands that switch repositories with `cd`, `git -C`, or repository overrides inside the same Bash call; invoke shipping directly from the protected repo.

`--stop` optionally installs a Claude Stop hook:

```bash
codegate install --claude --git --stop
```

It checks before Claude's first completion attempt and gives one repair opportunity. It does not block repeatedly when `stop_hook_active` is set, preventing an infinite loop. **This optional Stop integration is feedback, not a hard completion guarantee.** Commit/push gates remain independent.

### Git

The installer adds `pre-commit` and `pre-push` hooks. Existing executable hooks are backed up and chained after CodeGate succeeds. Their failure still blocks the operation. Non-executable prior hooks are preserved but not executed, matching Git's normal behavior.

- Commit: all tracked changes must be staged, and untracked files must be added or ignored. This prevents checking a worktree that differs from the staged code. `git commit -am` with unstaged changes is intentionally rejected; stage explicitly first.
- Push: index/tracked worktree must be clean and no nonignored untracked files may affect checks. The hook accepts pushed commit refs only when they point to current HEAD; pushing another branch's untested commit is rejected. Tag-object pushes are not supported. Ref deletions still run the gate.
- Git submodules/nested tracked directories require separate checking and are rejected rather than silently trusted.
- Inputs are hashed before and after checks. If tests modify nonignored source/config/index inputs, the result fails. Put generated files in `.gitignore`, and review auto-formatting changes before retrying.
- Passing results are never cached as future shipping authorization.

`core.hooksPath`/Husky/pre-commit configurations are **not overwritten**. Install with `--claude` only, then call `python3 .codegate/runner.py check --mode commit` or `--mode push` from your existing hook manager. Linked Git worktree installation is not supported in v0.1; install/manage hooks deliberately from the main checkout.

Local hooks can be disabled, removed, or bypassed with Git options. If you need enforcement against bypass, require trusted CI status checks and branch protection on the server.

## Claude Desktop, Codex, ChatGPT and MCP

Git hooks work independently of the AI client, including a local Codex workflow. They do not control ChatGPT's browser UI or code someone copies elsewhere.

For a client supporting **local stdio MCP servers**, print its configuration:

```bash
codegate mcp-config
```

Merge the printed `mcpServers` entry into that client's configuration. It exposes `codegate_check`. Its optional `path` argument (an absolute path inside a Git repository) defaults to the repository given with `--repo`, or to the server's working directory if none was given. `codegate mcp --require-path` makes the argument mandatory. Codex users can also register the server with `codex mcp add codegate -- python3 /path/to/repo/.codegate/runner.py --repo /path/to/repo mcp`. The minimal server implements initialize, ping, tools/list and tools/call using MCP protocol version 2024-11-05. Protocol behavior is covered by automated JSON-RPC tests; live client onboarding is not yet end-to-end tested.

MCP lets an assistant **ask** for results; it does not force it to call the tool or block shipping. Use Git hooks and required CI for enforcement. ChatGPT web connectors cannot run this local stdio server directly. The Codex plugin above covers the ChatGPT desktop app; no claim of a universal ChatGPT plugin is made.

## CI: enforce where local hooks can be bypassed

After committing `.codegate/runner.py`, a CI job can run:

```bash
python3 .codegate/runner.py check --json
```

Provision your project's language runtime and dependencies first. A minimal workflow for a stdlib-only Python unittest project is included in `examples/codegate-unittest.yml`. Adapt environment provisioning to the actual project; do not copy it blindly into a Node/service project.

Make the CI check required in your hosting platform's branch protections. Protect the gate runner, policy, workflow and test files with review ownership. A PR that can replace its own checks can otherwise report meaningless success. Required checks and branch rules must be configured by a repository administrator; this local tool does not set them remotely.

## Diagnostics and removal

```bash
codegate doctor
codegate check --json
codegate uninstall
```

Last result: `.git/codegate/report.json` (owner-readable file). Hook receipts/backups: `.git/codegate/`. Output can include private project details, so review before sharing it.

Uninstall removes only its recorded Claude entries, restores original Git hooks when the installed wrapper is unchanged, and preserves unrelated settings. If a wrapper was modified later, it warns and leaves it untouched. Config, vendored runner, reports and local ignore entry are retained for explicit cleanup. Existing project/global settings are not reset wholesale.

## Built-in checks and limits

Built-ins check merge conflicts, Git whitespace errors, Python syntax and a narrow set of obvious credential/private-key patterns. They inspect nonignored tracked/untracked files; secret inspection skips files above 2 MiB and symlinks. Syntax checking rejects Python files above that limit. Snapshot hashing is capped at 512 MiB. Ignored dependencies, ignored inputs, symlink target content, external services, ambient environment changes and time-of-check/time-of-use races are not fully covered.

This is not comprehensive secret detection, a vulnerability scanner, semantic correctness checking or a tamper-resistant policy engine. Use dedicated scanners and reviewed tests. Checks can have false positives; fix the policy deliberately rather than assuming PASS means safe production software.

## Development

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python --no-deps -e .
.venv/bin/python -m unittest discover -s tests -v
```

Tests include real temporary-repo commits and pushes to a local bare Git remote. No network push or model call is required. Claude hook behavior is tested with documented input/output payloads, not a live Claude session. See `VALIDATION.md` for the final run record.

Official hook contract used: https://code.claude.com/docs/en/hooks .

## Contributing and security

Contributions are welcome under the MIT license. Read [CONTRIBUTING.md](CONTRIBUTING.md) before sending a pull request. For vulnerabilities, follow [SECURITY.md](SECURITY.md); do not publish exploit details in an issue. This project is provided as-is, with no security certification.
