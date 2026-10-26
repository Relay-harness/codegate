# Developer onboarding

1. Install this local release once:

```bash
uv tool install git+https://github.com/Relay-harness/codegate.git
```

For a shared copy, run `uv tool install .` inside its extracted directory instead.

2. Open your application's Git repository. Run:

```bash
codegate init --claude --git
```

3. Review generated `codegate.toml`. It must run the actual project test/lint commands. Install the application's usual dependencies yourself. Run:

```bash
codegate doctor
codegate check
```

4. Stage `.codegate/runner.py`, `codegate.toml` and your intended code. Keep generated files ignored. Restart/reload Claude Code and confirm the hook in `/hooks`. Use Claude Code 2.1.295+ for fail-closed hook error/timeout handling.

5. Work normally. A failing gate explains the failure to Claude and prevents normal Git commit/push paths. Fix the issue and retry. Teammates bootstrap with `python3 .codegate/runner.py install --claude --git` after cloning.

For required enforcement, run the committed runner in CI and protect the branch with a required status check. Local hooks can be bypassed. The normal ChatGPT web interface is not controlled by this tool.

Remove local integrations with `codegate uninstall`. Full behavior and limits: README.md.
