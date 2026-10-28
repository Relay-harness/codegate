"""CodeGate: local, deterministic quality gates. Python 3.11+, no runtime deps."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shlex
import shutil
import signal
import subprocess
import sys
import time
import tomllib

VERSION = "0.1.1"
MARKER = "codegate-managed-v1"
MAX_OUTPUT = 1_000_000
MAX_INPUT_BYTES = 512 * 1024 * 1024
SECRET_PATTERNS = [
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{36,255}\b"),
    re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{60,255}\b"),
]


class GateError(Exception):
    pass


def git(repo, *args, input=None, ok=True):
    result = subprocess.run(["git", "-C", str(repo), *args], input=input,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    if ok and result.returncode:
        raise GateError("Git failed: " + result.stderr.decode(errors="replace")[-1500:])
    return result


def repository(path):
    path = Path(path).resolve()
    result = git(path, "rev-parse", "--show-toplevel")
    return Path(os.fsdecode(result.stdout).strip()).resolve()


def state_dir(repo):
    path = os.fsdecode(git(repo, "rev-parse", "--git-path", "codegate").stdout).strip()
    return (repo / path).resolve()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    temp.write_text(json.dumps(value, indent=2) + "\n")
    temp.chmod(0o600)
    os.replace(temp, path)


def config(repo):
    path = repo / "codegate.toml"
    if not path.is_file():
        raise GateError("No codegate.toml. Run codegate init first.")
    try:
        cfg = tomllib.loads(path.read_text())
    except (ValueError, OSError) as exc:
        raise GateError(f"Invalid codegate.toml: {exc}") from exc
    if cfg.get("version") != 1:
        raise GateError("codegate.toml must declare version = 1")
    unknown = set(cfg) - {"version", "timeout", "secret_scan", "python_syntax", "ship_commands", "checks"}
    if unknown:
        raise GateError("Unknown config fields: " + ", ".join(sorted(unknown)))
    for flag in ("secret_scan", "python_syntax"):
        if flag in cfg and type(cfg[flag]) is not bool:
            raise GateError(flag + " must be true or false")
    prefixes = cfg.get("ship_commands", [])
    if not isinstance(prefixes, list) or not all(isinstance(x, str) and x for x in prefixes):
        raise GateError("ship_commands must be an array of nonempty strings")
    checks = cfg.get("checks", [])
    if not isinstance(checks, list) or not checks:
        raise GateError("No project checks configured. Add at least one [[checks]] command; built-in checks alone cannot approve shipping.")
    for check in checks:
        if not isinstance(check, dict):
            raise GateError("Each check must be a table")
        if set(check) - {"name", "command", "timeout"}:
            raise GateError("Unknown check fields; supported fields are name, command, timeout")
        if "name" in check and not isinstance(check["name"], str):
            raise GateError("Check names must be strings")
        cmd = check.get("command")
        if not isinstance(cmd, list) or not cmd or not all(isinstance(s, str) and s for s in cmd):
            raise GateError("Each check.command must be a nonempty array of strings (not a shell string)")
        timeout = check.get("timeout", 120)
        if type(timeout) not in (int, float) or not 0 < timeout <= 600:
            raise GateError("Check timeouts must be between 0 and 600 seconds")
    budget = cfg.get("timeout", 300)
    if type(budget) not in (int, float) or not 0 < budget <= 600:
        raise GateError("Total timeout must be between 0 and 600 seconds")
    return cfg


def files(repo):
    raw = git(repo, "ls-files", "--cached", "--others", "--exclude-standard", "-z").stdout
    return sorted({os.fsdecode(x) for x in raw.split(b"\0") if x})


def snapshot(repo):
    digest = hashlib.sha256()
    digest.update(git(repo, "rev-parse", "--verify", "HEAD", ok=False).stdout)
    digest.update(git(repo, "ls-files", "--stage", "-z").stdout)
    total = 0
    names = files(repo)
    for name in names:
        p = repo / name
        digest.update(os.fsencode(name) + b"\0")
        if p.is_symlink():
            digest.update(b"link:" + os.fsencode(os.readlink(p)))
        elif p.is_file():
            with p.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_INPUT_BYTES:
                        raise GateError("Repository scan exceeds 512 MiB. Ignore generated/vendor files before using CodeGate.")
                    digest.update(chunk)
        elif p.is_dir():
            # Git submodule contents require their own checks, not a silent pass.
            raise GateError(f"Nested tracked directory/submodule needs an independent gate: {name}")
        else:
            digest.update(b"missing")
    cfg = repo / "codegate.toml"
    digest.update(cfg.read_bytes() if cfg.exists() else b"no-config")
    return digest.hexdigest(), names


def kill_group(proc):
    if os.name == "posix":
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    else:
        proc.kill()
    proc.wait(timeout=5)


def run_command(command, repo, timeout):
    """Bounded POSIX runner: cap time and retained output; kill owned process group."""
    started = time.monotonic()
    if os.name != "posix":
        return {"ok": False, "output": "This release requires macOS/Linux (POSIX process-group cleanup).", "duration": 0}
    env = {**os.environ, "CI": "1", "CODEGATE_ACTIVE": "1"}
    try:
        proc = subprocess.Popen(command, cwd=repo, env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
    except OSError as exc:
        return {"ok": False, "output": str(exc), "duration": round(time.monotonic() - started, 3)}
    output = bytearray()
    reason = None
    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ)
    try:
        while selector.get_map():
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                reason = f"Check timed out after {timeout:.1f}s"
                break
            for key, _ in selector.select(min(remaining, 0.2)):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                available = MAX_OUTPUT - len(output)
                output.extend(chunk[:available])
                if len(chunk) > available:
                    reason = "Check exceeded the 1 MB output budget"
                    break
            if reason:
                break
        if reason:
            kill_group(proc)
        else:
            remaining = max(0.01, timeout - (time.monotonic() - started))
            try:
                proc.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                reason = "Check timed out after closing output"
                kill_group(proc)
            # Clean remaining group members even if the leader exited normally.
            if os.name == "posix":
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
    finally:
        selector.close()
        proc.stdout.close()
        if proc.poll() is None:
            kill_group(proc)
    raw_output = bytes(output)
    for pattern in SECRET_PATTERNS:
        raw_output = pattern.sub(b"[REDACTED]", raw_output)
    text = raw_output.decode(errors="replace")
    if reason:
        text += "\n" + reason
    return {"ok": not reason and proc.returncode == 0, "returncode": proc.returncode,
            "output": text[-12000:], "duration": round(time.monotonic() - started, 3)}


def builtin_checks(repo, names, cfg, mode):
    failures = []
    if git(repo, "ls-files", "--unmerged", "-z").stdout:
        failures.append("Resolve merge conflicts before running the gate.")
    if mode in ("commit", "push"):
        args = ["diff", "--quiet"] if mode == "commit" else ["diff", "HEAD", "--quiet"]
        if git(repo, *args, ok=False).returncode:
            failures.append("Stage all intended changes before commit; push requires a clean tracked worktree and index.")
        if git(repo, "ls-files", "--others", "--exclude-standard", "-z").stdout:
            failures.append("Untracked files may affect tests. Add intended files or ignore generated files before shipping.")
    for args in [("diff", "--check"), ("diff", "--cached", "--check")]:
        result = git(repo, *args, ok=False)
        if result.returncode:
            failures.append(result.stdout.decode(errors="replace")[-3000:] or "Git whitespace check failed")
    for name in names:
        p = repo / name
        if not p.is_file() or p.is_symlink():
            continue
        if p.stat().st_size > 2 * 1024 * 1024:
            if p.suffix == ".py":
                failures.append(f"Python file exceeds 2 MiB scan limit: {name}")
            continue
        data = p.read_bytes()
        if cfg.get("secret_scan", True) and any(pattern.search(data) for pattern in SECRET_PATTERNS):
            failures.append(f"Possible credential/private key in {name}. Remove it and rotate any exposed credential. Value redacted.")
        if cfg.get("python_syntax", True) and p.suffix == ".py":
            try:
                compile(data, name, "exec", ast.PyCF_ONLY_AST)
            except (SyntaxError, ValueError) as exc:
                failures.append(f"Python syntax failed: {name}:{getattr(exc, 'lineno', '?')} {getattr(exc, 'msg', type(exc).__name__)}")
    return {"name": "built-in checks", "ok": not failures, "output": "\n".join(failures), "duration": 0}


def check(repo, mode="worktree"):
    started = time.monotonic()
    results = []
    report = {"version": VERSION, "ok": False, "mode": mode, "checks": results}
    try:
        if os.environ.get("CODEGATE_ACTIVE"):
            raise GateError("Recursive CodeGate execution inside a check is blocked")
        cfg = config(repo)
        before, names = snapshot(repo)
        report["fingerprint"] = before
        results.append(builtin_checks(repo, names, cfg, mode))
        if results[-1]["ok"]:
            for spec in cfg["checks"]:
                remaining = cfg.get("timeout", 300) - (time.monotonic() - started)
                if remaining <= 0:
                    results.append({"name": spec.get("name", "project check"), "ok": False, "output": "Total gate deadline exceeded"})
                    break
                result = run_command(spec["command"], repo, min(spec.get("timeout", 120), remaining))
                results.append({"name": spec.get("name", shlex.join(spec["command"])), **result})
                if not result["ok"]:
                    break
        after, _ = snapshot(repo)
        if after != before:
            results.append({"name": "input stability", "ok": False, "output": "Repository inputs changed during checks. Review changes and run the gate again."})
        report["ok"] = bool(results) and all(x["ok"] for x in results)
    except (GateError, OSError, subprocess.SubprocessError) as exc:
        results.append({"name": "gate setup", "ok": False, "output": str(exc)})
    report["duration"] = round(time.monotonic() - started, 3)
    atomic_json(state_dir(repo) / "report.json", report)
    return report


def format_report(report):
    lines = ["CodeGate: " + ("PASS" if report["ok"] else "BLOCKED")]
    for result in report["checks"]:
        lines.append(("  PASS " if result["ok"] else "  FAIL ") + result["name"])
        if not result["ok"] and result.get("output"):
            lines.append(result["output"][-6000:])
    if not report["ok"]:
        lines.append("Fix the failures, then rerun the same action. Do not bypass the gate.")
    return "\n".join(lines)


def shipping_command(command, cfg):
    """Conservative convenience detection, NOT an adversarial shell security parser."""
    if re.search(r"\bgit\b[^\n;&|]*\b(commit|push)\b", command):
        return "git"
    if re.search(r"\bgh\s+pr\s+(create|merge)\b", command):
        return "pr"
    for prefix in cfg.get("ship_commands", []):
        if isinstance(prefix, str) and prefix and prefix in command:
            return "custom"
    return None


def claude_hook(repo, raw=None):
    try:
        payload = json.load(sys.stdin) if raw is None else json.loads(raw)
        if not isinstance(payload, dict):
            raise GateError("Hook payload must be an object")
        event = payload.get("hook_event_name", "PreToolUse")
        if event == "Stop":
            # One repair opportunity, not an unbounded stop-hook loop.
            if payload.get("stop_hook_active"):
                return 0
            report = check(repo)
            if not report["ok"]:
                print(json.dumps({"decision": "block", "reason": format_report(report)}))
            return 0
        tool = payload.get("tool_input", {})
        if not isinstance(tool, dict):
            raise GateError("tool_input must be an object")
        command = tool.get("command", "")
        if not isinstance(command, str):
            raise GateError("Bash command must be a string")
        # Missing/invalid policy blocks ship-looking commands, not every read/edit.
        candidate = re.search(r"\b(commit|push|deploy|publish)\b|\bgh\s+pr\b", command)
        try:
            cfg = config(repo)
        except GateError:
            if not candidate:
                return 0
            raise
        kind = shipping_command(command, cfg)
        if not kind:
            return 0
        cwd = repository(payload.get("cwd", repo))
        if cwd != repo or re.search(r"\bcd\s|\bgit\s+[^\n;&|]*(-C\b|--git-dir|--work-tree)", command):
            raise GateError("Run shipping commands from this repository directly, without cd/git -C or repository overrides in the same command.")
        if os.environ.get("CODEGATE_ACTIVE"):
            raise GateError("Recursive shipping from a check is not allowed")
        report = check(repo, "commit" if kind == "git" and re.search(r"\bcommit\b", command) else "worktree")
        if not report["ok"]:
            raise GateError(format_report(report))
        return 0  # No permission grant: preserve Claude's normal permission flow.
    except (ValueError, GateError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": str(exc)}}))
        return 0


def plugin_hook():
    """Claude Code/Codex plugin hook. Plugins load in every project, so act only where this checkout opted in:
    codegate.toml plus a local install receipt, so a cloned repository cannot make the plugin run its commands."""
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
        repo = repository(payload.get("cwd") or os.getcwd())
        receipt = state_dir(repo) / "install.json"
        if not (repo / "codegate.toml").is_file() or not receipt.is_file():
            return 0
        if json.loads(receipt.read_text()).get("claude"):
            return 0  # A project-local `install --claude` hook already gates this repository.
    except (ValueError, AttributeError, TypeError, GateError, OSError, subprocess.SubprocessError):
        return 0  # Not a Git repository or not opted in: leave the command alone.
    return claude_hook(repo, raw)


def detect_checks(repo):
    checks = []
    package = repo / "package.json"
    if package.exists():
        try:
            scripts = json.loads(package.read_text()).get("scripts", {})
        except (ValueError, OSError) as exc:
            raise GateError(f"Cannot read package.json: {exc}") from exc
        manager = "pnpm" if (repo / "pnpm-lock.yaml").exists() else "yarn" if (repo / "yarn.lock").exists() else "bun" if any((repo / p).exists() for p in ("bun.lock", "bun.lockb")) else "npm"
        for name in ("lint", "typecheck", "test", "build"):
            if name in scripts:
                checks.append({"name": name, "command": [manager, "run", name], "timeout": 120})
    if (repo / "pyproject.toml").exists() or (repo / "pytest.ini").exists():
        python = ".venv/bin/python" if (repo / ".venv/bin/python").exists() else "python3"
        if (repo / "tests").is_dir() or (repo / "pytest.ini").exists():
            checks.append({"name": "Python tests", "command": [python, "-m", "pytest", "-q"], "timeout": 120})
    return checks


def init_config(repo):
    path = repo / "codegate.toml"
    if path.exists():
        return
    checks = detect_checks(repo)
    text = '# Project commands run with your user permissions. Review before running.\nversion = 1\ntimeout = 300\nsecret_scan = true\npython_syntax = true\n# Extra Bash ship command prefixes (for example: "npm publish").\nship_commands = []\n'
    for item in checks:
        text += '\n[[checks]]\nname = ' + json.dumps(item["name"]) + '\ncommand = ' + json.dumps(item["command"]) + '\ntimeout = 120\n'
    if not checks:
        text += '\n# No test runner detected. Add [[checks]] before CodeGate will allow shipping.\n# See README for Python unittest and Node examples.\n'
    path.write_text(text)


def install(repo, claude=False, git_hooks=False, stop=False):
    if os.name != "posix":
        raise GateError("Hook installation currently supports macOS/Linux only")
    # Refuse unsupported Git setups before writing any integration files.
    if git_hooks:
        if git(repo, "config", "--get", "core.hooksPath", ok=False).returncode == 0:
            raise GateError("core.hooksPath is configured. Use your hook manager to call `.codegate/runner.py check` instead; CodeGate will not replace it.")
        actual = Path(os.fsdecode(git(repo, "rev-parse", "--absolute-git-dir").stdout).strip()).resolve()
        shared = Path(os.fsdecode(git(repo, "rev-parse", "--git-common-dir").stdout).strip())
        if actual != (repo / shared).resolve():
            raise GateError("Install Git hooks in the main checkout, not a linked worktree")
        for hook_name in ("pre-commit", "pre-push"):
            if (actual / "hooks" / hook_name).is_symlink():
                raise GateError("Existing symlink Git hooks must be integrated manually")
    runner = repo / ".codegate/runner.py"
    if runner.is_symlink() or runner.parent.is_symlink():
        raise GateError("Refusing a symlink runner path")
    runner.parent.mkdir(exist_ok=True)
    source = Path(__file__).resolve()
    if source != runner.resolve():
        if runner.exists() and MARKER not in runner.read_text():
            raise GateError("Refusing to replace an existing .codegate/runner.py")
        shutil.copyfile(source, runner)
    init_config(repo)
    state = state_dir(repo)
    state.mkdir(parents=True, exist_ok=True)
    receipt_path = state / "install.json"
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {"hooks": {}, "claude": []}
    base = shlex.join([sys.executable, str(runner), "--repo", str(repo)])
    if claude or stop:
        settings = repo / ".claude/settings.local.json"
        settings.parent.mkdir(exist_ok=True)
        old = settings.read_text() if settings.exists() else None
        data = json.loads(old) if old else {}
        if not isinstance(data, dict) or not isinstance(data.get("hooks", {}), dict):
            raise GateError("Claude local settings/hooks must be JSON objects")
        if old and not (state / "claude-settings.original.json").exists():
            (state / "claude-settings.original.json").write_text(old)
        for event, matcher in [("PreToolUse", "Bash")] + ([("Stop", None)] if stop else []):
            handler = {"type": "command", "command": sys.executable,
                       "args": [str(runner), "--repo", str(repo), "hook", "claude"], "timeout": 615}
            if event == "PreToolUse":
                handler["onFailure"] = "block"
            entry = {"hooks": [handler]}
            if matcher:
                entry["matcher"] = matcher
            entries = data.setdefault("hooks", {}).setdefault(event, [])
            if not isinstance(entries, list):
                raise GateError("Claude hook entries must be lists")
            for previous in receipt["claude"]:
                if previous["event"] == event and previous["entry"] != entry and previous["entry"] in entries:
                    entries.remove(previous["entry"])
            receipt["claude"] = [item for item in receipt["claude"] if item["event"] != event]
            if entry not in entries:
                entries.append(entry)
            record = {"event": event, "entry": entry}
            if record not in receipt["claude"]:
                receipt["claude"].append(record)
        atomic_json(settings, data)
        atomic_json(receipt_path, receipt)
        exclude = Path(os.fsdecode(git(repo, "rev-parse", "--git-path", "info/exclude").stdout).strip())
        if not exclude.is_absolute():
            exclude = repo / exclude
        exclude.parent.mkdir(parents=True, exist_ok=True)
        existing = exclude.read_text() if exclude.exists() else ""
        line = "/.claude/settings.local.json"
        if line not in existing.splitlines():
            with exclude.open("a") as stream:
                stream.write("\n" + line + "\n")
    if git_hooks:
        if git(repo, "config", "--get", "core.hooksPath", ok=False).returncode == 0:
            raise GateError("core.hooksPath is configured. Use your hook manager to call `.codegate/runner.py check` instead; CodeGate will not replace it.")
        git_dir = Path(os.fsdecode(git(repo, "rev-parse", "--absolute-git-dir").stdout).strip()).resolve()
        common = Path(os.fsdecode(git(repo, "rev-parse", "--git-common-dir").stdout).strip())
        common = (repo / common).resolve()
        if git_dir != common:
            raise GateError("Install Git hooks in the main checkout, not a linked worktree")
        hooks = git_dir / "hooks"
        hooks.mkdir(exist_ok=True)
        for name in ("pre-commit", "pre-push"):
            path = hooks / name
            if path.exists() and MARKER not in path.read_text(errors="replace"):
                if name in receipt["hooks"]:
                    raise GateError(f"Existing {name} changed since installation; refusing replacement")
                backup = state / "previous-hooks" / name
                backup.parent.mkdir(exist_ok=True)
                shutil.copy2(path, backup)
                receipt["hooks"][name] = str(backup)
            elif name not in receipt["hooks"]:
                receipt["hooks"][name] = None
            wrapper = '#!/bin/sh\n# ' + MARKER + '\nexec ' + base + ' git-hook ' + name + ' "$@"\n'
            expected_hash = receipt.get("wrapper_hashes", {}).get(name)
            if path.exists() and expected_hash and hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
                raise GateError(f"Installed {name} was modified; refusing to overwrite it")
            path.write_text(wrapper)
            receipt.setdefault("wrapper_hashes", {})[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            path.chmod(0o755)
            atomic_json(receipt_path, receipt)
    atomic_json(receipt_path, receipt)
    print("CodeGate installed. Review codegate.toml, then stage .codegate/runner.py and codegate.toml.")
    print("No dependencies were installed in your project. Existing Git hooks are chained after the gate.")
    if claude:
        print("Claude Code 2.1.295+ is required for fail-closed onFailure handling. Reload hooks and verify with /hooks.")
    if not detect_checks(repo) and not tomllib.loads((repo / "codegate.toml").read_text()).get("checks"):
        print("ACTION REQUIRED: no test runner detected. Configure at least one check; shipping remains blocked.")


def uninstall(repo):
    state = state_dir(repo)
    receipt_path = state / "install.json"
    if not receipt_path.exists():
        raise GateError("No CodeGate installation receipt in this repository")
    receipt = json.loads(receipt_path.read_text())
    if receipt.get("claude"):
        path = repo / ".claude/settings.local.json"
        if path.exists():
            data = json.loads(path.read_text())
            for item in receipt["claude"]:
                entries = data.get("hooks", {}).get(item["event"], [])
                if item["entry"] in entries:
                    entries.remove(item["entry"])
            atomic_json(path, data)
        receipt["claude"] = []
    git_dir = Path(os.fsdecode(git(repo, "rev-parse", "--absolute-git-dir").stdout).strip())
    pending = {}
    for name, backup in receipt.get("hooks", {}).items():
        path = git_dir / "hooks" / name
        expected = receipt.get("wrapper_hashes", {}).get(name)
        if path.is_symlink() or (path.exists() and (not expected or hashlib.sha256(path.read_bytes()).hexdigest() != expected)):
            pending[name] = backup
            print(f"Kept modified hook: {path}", file=sys.stderr)
            continue
        if backup:
            shutil.copy2(backup, path)
        elif path.exists():
            path.unlink()
    receipt["hooks"] = pending
    atomic_json(receipt_path, receipt)
    print("Removed owned integrations; preserved config, runner, reports and unrelated settings. Modified hooks, if any, were left untouched.")


def git_hook(repo, name, args):
    if os.environ.get("CODEGATE_ACTIVE"):
        raise GateError("Recursive commit/push inside a check is blocked")
    raw = sys.stdin.buffer.read() if name == "pre-push" else b""
    if name == "pre-push":
        head = git(repo, "rev-parse", "HEAD").stdout.strip()
        for line in raw.splitlines():
            fields = line.split()
            if len(fields) != 4:
                raise GateError("Invalid pre-push ref input")
            oid = fields[1]
            if set(oid) != {48} and oid != head:
                raise GateError("This gate validates HEAD only. Push each branch/tag from its checked-out commit; non-HEAD ref push blocked.")
    report = check(repo, "commit" if name == "pre-commit" else "push")
    print(format_report(report), file=sys.stderr)
    if not report["ok"]:
        return 1
    receipt = state_dir(repo) / "install.json"
    old = json.loads(receipt.read_text()).get("hooks", {}).get(name) if receipt.exists() else None
    if old and os.access(old, os.X_OK):
        result = subprocess.run([old, *args], cwd=repo, input=raw, timeout=600)
        return result.returncode
    return 0


def mcp_server(path, require_path=False):
    """Minimal JSON-RPC MCP stdio server. Check is read/exec, not a shipping authorization.
    The repository is resolved per call so a plugin-launched server starts outside Git too."""
    for line in sys.stdin:
        request = None
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("JSON-RPC request must be an object")
            rid = request.get("id")
            method = request.get("method")
            if rid is None:
                continue
            if method == "initialize":
                result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "codegate", "version": VERSION}}
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                where = "Required." if require_path else "Defaults to the server's working directory."
                result = {"tools": [{"name": "codegate_check", "description": "Run a repository's configured CodeGate quality checks (codegate.toml). Use when the user requests repository checks or before a shipping operation in an opted-in repository. Commands run with host permissions and inherited environment, may change files or use the network, and are not a sandbox or proof of bug-free code.", "inputSchema": {"type": "object", "properties": {"path": {"type": "string", "description": "Absolute path inside the Git repository to check. " + where}}, "additionalProperties": False}, "annotations": {"title": "Run configured repository checks", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True}}]}
            elif method == "tools/call":
                params = request.get("params", {})
                arguments = params.get("arguments") or {}
                if params.get("name") != "codegate_check" or not isinstance(arguments, dict) or set(arguments) - {"path"} or not isinstance(arguments.get("path", ""), str):
                    raise GateError("Unknown tool or arguments")
                target = arguments.get("path") or (None if require_path else path)
                if not target:
                    raise GateError("Pass path: an absolute path inside the Git repository to check")
                if "path" in arguments and not Path(target).is_absolute():
                    raise GateError("path must be absolute")
                report = check(repository(target))
                result = {"content": [{"type": "text", "text": format_report(report)}], "isError": not report["ok"]}
            else:
                print(json.dumps({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "Method not found"}}), flush=True)
                continue
            print(json.dumps({"jsonrpc": "2.0", "id": rid, "result": result}), flush=True)
        except Exception as exc:
            print(json.dumps({"jsonrpc": "2.0", "id": request.get("id") if isinstance(request, dict) else None, "error": {"code": -32603, "message": str(exc)}}), flush=True)


def doctor(repo):
    findings = []
    try:
        cfg = config(repo)
        findings.append({"name": "configuration", "ok": True})
        for spec in cfg["checks"]:
            exe = spec["command"][0]
            found = (repo / exe).is_file() if "/" in exe else bool(shutil.which(exe))
            findings.append({"name": spec.get("name", exe) + " executable", "ok": found})
    except GateError as exc:
        findings.append({"name": "configuration", "ok": False, "detail": str(exc)})
    receipt_path = state_dir(repo) / "install.json"
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    git_dir = Path(os.fsdecode(git(repo, "rev-parse", "--absolute-git-dir").stdout).strip())
    for name in ("pre-commit", "pre-push"):
        path = git_dir / "hooks" / name
        expected = receipt.get("wrapper_hashes", {}).get(name)
        findings.append({"name": name + " installed", "ok": bool(path.is_file() and expected and hashlib.sha256(path.read_bytes()).hexdigest() == expected)})
    settings = repo / ".claude/settings.local.json"
    data = json.loads(settings.read_text()) if settings.exists() else {}
    registered = [item for item in receipt.get("claude", []) if item["event"] == "PreToolUse"]
    findings.append({"name": "Claude Bash hook installed", "ok": bool(registered) and all(item["entry"] in data.get("hooks", {}).get(item["event"], []) for item in registered)})
    for item in findings:
        print(("OK   " if item["ok"] else "WARN ") + item["name"] + (": " + item["detail"] if item.get("detail") else ""))
    print("Doctor checks setup, not test correctness. Run codegate check for quality results.")
    return 0 if all(item["ok"] for item in findings) else 1


def main():
    parser = argparse.ArgumentParser(description="CodeGate: checks before AI-assisted shipping")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--version", action="version", version=VERSION)
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("init", "install"):
        cmd = sub.add_parser(action)
        cmd.add_argument("--claude", action="store_true")
        cmd.add_argument("--git", action="store_true", dest="git_hooks")
        cmd.add_argument("--stop", action="store_true", help="Optional one-retry Claude completion check")
    cmd = sub.add_parser("check")
    cmd.add_argument("--json", action="store_true")
    cmd.add_argument("--mode", choices=["worktree", "commit", "push"], default="worktree")
    sub.add_parser("uninstall")
    sub.add_parser("doctor")
    cmd = sub.add_parser("mcp")
    cmd.add_argument("--require-path", action="store_true", help="Plugin hosts that start servers outside the project")
    sub.add_parser("mcp-config")
    cmd = sub.add_parser("hook")
    cmd.add_argument("client", choices=["claude", "plugin"])
    cmd = sub.add_parser("git-hook")
    cmd.add_argument("kind", choices=["pre-commit", "pre-push"])
    cmd.add_argument("hook_args", nargs="*")
    args = parser.parse_args()
    # Plugin entry points can start outside a Git repository; they resolve it themselves.
    if args.action == "hook" and args.client == "plugin":
        return plugin_hook()
    if args.action == "mcp":
        mcp_server(args.repo, args.require_path)
        return 0
    try:
        repo = repository(args.repo)
        if args.action in ("init", "install"):
            install(repo, args.claude, args.git_hooks, args.stop)
            return 0
        if args.action == "uninstall":
            uninstall(repo)
            return 0
        if args.action == "doctor":
            return doctor(repo)
        if args.action == "check":
            report = check(repo, args.mode)
            print(json.dumps(report, indent=2) if args.json else format_report(report))
            return 0 if report["ok"] else 1
        if args.action == "hook":
            return claude_hook(repo)
        if args.action == "git-hook":
            return git_hook(repo, args.kind, args.hook_args)
        if args.action == "mcp-config":
            print(json.dumps({"mcpServers": {"codegate": {"command": sys.executable, "args": [str(repo / ".codegate/runner.py"), "--repo", str(repo), "mcp"]}}}, indent=2))
            return 0
    except (GateError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"CodeGate: BLOCKED: {exc}", file=sys.stderr)
        return 2 if args.action == "hook" else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
