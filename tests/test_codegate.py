import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import codegate as cg


class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name).resolve()
        self.envpatch = patch.dict(os.environ)
        self.envpatch.start()
        os.environ.pop("CODEGATE_ACTIVE", None)
        for name in list(os.environ):
            if name.startswith("GIT_"):
                os.environ.pop(name)
        self.run_git("init", "-q")
        self.run_git("config", "user.name", "CodeGate Tests")
        self.run_git("config", "user.email", "codegate@example.invalid")
        (self.repo / ".gitignore").write_text("__pycache__/\n*.pyc\n.cache/\n")
        self.write_config()
        (self.repo / "app.py").write_text("value = 1\n")

    def tearDown(self):
        self.envpatch.stop()
        self.temp.cleanup()

    def run_git(self, *args, check=True, input=None):
        result = subprocess.run(["git", "-C", str(self.repo), *args], input=input, capture_output=True)
        if check and result.returncode:
            self.fail(result.stderr.decode())
        return result

    def write_config(self, command=None, timeout=3, extra=""):
        command = command or [sys.executable, "-c", "print('tests passed')"]
        (self.repo / "codegate.toml").write_text('version = 1\ntimeout = 10\n' + extra + '\n[[checks]]\nname = "test suite"\ncommand = ' + json.dumps(command) + '\ntimeout = ' + str(timeout) + '\n')

    def install(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            cg.install(self.repo, **kwargs)

    def hook(self, command, **extra):
        payload = {"hook_event_name": "PreToolUse", "cwd": str(self.repo), "tool_input": {"command": command}, **extra}
        out = io.StringIO()
        with patch("sys.stdin", io.StringIO(json.dumps(payload))), contextlib.redirect_stdout(out):
            code = cg.claude_hook(self.repo)
        return code, out.getvalue()

    def test_no_config_blocks(self):
        (self.repo / "codegate.toml").unlink()
        report = cg.check(self.repo)
        self.assertFalse(report["ok"])
        self.assertIn("No codegate.toml", cg.format_report(report))

    def test_empty_checks_block(self):
        (self.repo / "codegate.toml").write_text("version = 1\n")
        self.assertFalse(cg.check(self.repo)["ok"])

    def test_pass(self):
        self.assertTrue(cg.check(self.repo)["ok"])

    def test_command_failure(self):
        self.write_config([sys.executable, "-c", "raise SystemExit(3)"])
        report = cg.check(self.repo)
        self.assertFalse(report["ok"])
        self.assertEqual(report["checks"][-1]["returncode"], 3)

    def test_missing_binary(self):
        self.write_config(["codegate-nonexistent-binary-12345"])
        self.assertFalse(cg.check(self.repo)["ok"])

    def test_syntax(self):
        (self.repo / "app.py").write_text("def broken(:\n")
        report = cg.check(self.repo)
        self.assertFalse(report["ok"])
        self.assertIn("app.py", cg.format_report(report))

    def test_secret_is_redacted(self):
        secret = "AKIA" + "A" * 16
        (self.repo / "credential.txt").write_text(secret)
        report = cg.check(self.repo)
        self.assertFalse(report["ok"])
        self.assertNotIn(secret, json.dumps(report))
        self.assertIn("credential.txt", cg.format_report(report))

    def test_timeout(self):
        self.write_config([sys.executable, "-c", "import time; time.sleep(10)"], timeout=0.1)
        started = time.monotonic()
        self.assertFalse(cg.check(self.repo)["ok"])
        self.assertLess(time.monotonic() - started, 4)

    def test_output_budget(self):
        self.write_config([sys.executable, "-c", "print('x' * 1100000)"])
        report = cg.check(self.repo)
        self.assertFalse(report["ok"])
        self.assertIn("output budget", report["checks"][-1]["output"])

    def test_mutation_invalidates(self):
        self.write_config([sys.executable, "-c", "from pathlib import Path; Path('app.py').write_text('value = 2')"])
        report = cg.check(self.repo)
        self.assertFalse(report["ok"])
        self.assertEqual(report["checks"][-1]["name"], "input stability")

    def test_nonzero_timeout_rejected(self):
        self.write_config(timeout=0)
        self.assertFalse(cg.check(self.repo)["ok"])

    def test_shell_string_rejected(self):
        (self.repo / "codegate.toml").write_text('version = 1\n[[checks]]\ncommand = "echo yes"\n')
        self.assertFalse(cg.check(self.repo)["ok"])

    def test_recursive_gate_blocks(self):
        with patch.dict(os.environ, {"CODEGATE_ACTIVE": "1"}):
            self.assertFalse(cg.check(self.repo)["ok"])

    def test_commit_requires_staging(self):
        self.run_git("add", ".")
        self.assertTrue(cg.check(self.repo, "commit")["ok"])
        (self.repo / "app.py").write_text("value = 2\n")
        self.assertFalse(cg.check(self.repo, "commit")["ok"])

    def test_untracked_blocks_commit(self):
        self.assertFalse(cg.check(self.repo, "commit")["ok"])

    def test_claude_nonshipping_no_decision(self):
        code, text = self.hook("git status")
        self.assertEqual(code, 0)
        self.assertEqual(text, "")

    def test_claude_failure_denies(self):
        self.run_git("add", ".")
        self.write_config([sys.executable, "-c", "raise SystemExit(1)"])
        self.run_git("add", ".")
        code, text = self.hook("git commit -m test")
        data = json.loads(text)
        self.assertEqual(code, 0)
        self.assertEqual(data["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_claude_pass_does_not_grant_permissions(self):
        self.run_git("add", ".")
        _, text = self.hook("git commit -m test")
        self.assertEqual(text, "")

    def test_claude_missing_config_denies_ship(self):
        (self.repo / "codegate.toml").unlink()
        _, text = self.hook("git push")
        self.assertEqual(json.loads(text)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_claude_cd_denied(self):
        _, text = self.hook("cd ../other; git push")
        self.assertIn("without cd", text)

    def test_claude_stop_one_repair(self):
        self.write_config([sys.executable, "-c", "raise SystemExit(1)"])
        _, text = self.hook("", hook_event_name="Stop")
        self.assertEqual(json.loads(text)["decision"], "block")
        _, text = self.hook("", hook_event_name="Stop", stop_hook_active=True)
        self.assertEqual(text, "")

    def test_claude_merge_idempotent_uninstall_preserves_edits(self):
        settings = self.repo / ".claude/settings.local.json"
        settings.parent.mkdir()
        initial = {"permissions": {"allow": ["Bash(git status)"]}, "hooks": {"PreToolUse": [{"matcher": "Read", "hooks": []}]}}
        settings.write_text(json.dumps(initial))
        self.install(claude=True)
        self.install(claude=True)
        data = json.loads(settings.read_text())
        self.assertEqual(len(data["hooks"]["PreToolUse"]), 2)
        data["new_user_setting"] = True
        settings.write_text(json.dumps(data))
        with contextlib.redirect_stdout(io.StringIO()):
            cg.uninstall(self.repo)
        restored = json.loads(settings.read_text())
        self.assertEqual(restored["permissions"], initial["permissions"])
        self.assertEqual(restored["hooks"]["PreToolUse"], initial["hooks"]["PreToolUse"])
        self.assertTrue(restored["new_user_setting"])

    def test_custom_hookspath_refused_without_mutation(self):
        self.run_git("config", "core.hooksPath", "other-hooks")
        with self.assertRaises(cg.GateError):
            self.install(claude=True, git_hooks=True)
        self.assertFalse((self.repo / ".claude").exists())
        self.assertFalse((self.repo / ".codegate").exists())

    def test_existing_hooks_restored(self):
        hook = self.repo / ".git/hooks/pre-commit"
        text = "#!/bin/sh\nexit 0\n"
        hook.write_text(text)
        hook.chmod(0o755)
        self.install(git_hooks=True)
        self.install(git_hooks=True)
        with contextlib.redirect_stdout(io.StringIO()):
            cg.uninstall(self.repo)
        self.assertEqual(hook.read_text(), text)
        self.assertTrue(os.access(hook, os.X_OK))

    def test_real_git_commit_pass_and_failure(self):
        self.install(git_hooks=True)
        self.run_git("add", ".")
        result = self.run_git("commit", "-qm", "passing gate", check=False)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        (self.repo / "app.py").write_text("def broken(:\n")
        self.run_git("add", ".")
        result = self.run_git("commit", "-qm", "should block", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"BLOCKED", result.stderr)
        self.assertEqual(self.run_git("log", "-1", "--format=%s").stdout.strip(), b"passing gate")

    def test_prior_hook_failure_propagates(self):
        hook = self.repo / ".git/hooks/pre-commit"
        hook.write_text("#!/bin/sh\nexit 7\n")
        hook.chmod(0o755)
        self.install(git_hooks=True)
        self.run_git("add", ".")
        self.assertNotEqual(self.run_git("commit", "-qm", "blocked by prior", check=False).returncode, 0)

    def test_real_git_push_to_local_bare(self):
        self.install(git_hooks=True)
        self.run_git("add", ".")
        self.run_git("commit", "-qm", "initial")
        remote = self.repo.parent / (self.repo.name + "-remote.git")
        try:
            subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
            self.run_git("remote", "add", "origin", str(remote))
            self.assertEqual(self.run_git("push", "origin", "HEAD:refs/heads/main", check=False).returncode, 0)
            (self.repo / "app.py").write_text("value = 2\n")
            result = self.run_git("push", "origin", "HEAD:refs/heads/second", check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"BLOCKED", result.stderr)
        finally:
            import shutil
            shutil.rmtree(remote, ignore_errors=True)

    def test_nonhead_push_rejected(self):
        self.install(git_hooks=True)
        self.run_git("add", ".")
        self.run_git("commit", "-qm", "initial")
        executable = self.repo / ".codegate/runner.py"
        ref = "refs/heads/other " + "1" * 40 + " refs/heads/other " + "0" * 40 + "\n"
        result = subprocess.run([sys.executable, str(executable), "--repo", str(self.repo), "git-hook", "pre-push"], input=ref, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("HEAD only", result.stderr)

    def test_mcp_roundtrip(self):
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "codegate_check", "arguments": {}}},
        ]
        result = subprocess.run([sys.executable, str(Path(cg.__file__)), "--repo", str(self.repo), "mcp"], input="\n".join(map(json.dumps, requests)) + "\n", capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        messages = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[1]["result"]["tools"][0]["name"], "codegate_check")
        annotations = messages[1]["result"]["tools"][0]["annotations"]
        self.assertEqual(annotations["title"], "Run configured repository checks")
        self.assertFalse(annotations["readOnlyHint"])
        self.assertTrue(annotations["destructiveHint"])
        self.assertTrue(annotations["openWorldHint"])
        self.assertFalse(messages[2]["result"]["isError"])

    def test_modified_owned_hook_is_not_overwritten(self):
        self.install(git_hooks=True)
        hook = self.repo / ".git/hooks/pre-commit"
        changed = hook.read_text() + "# developer customization\n"
        hook.write_text(changed)
        with self.assertRaises(cg.GateError):
            self.install(git_hooks=True)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            cg.uninstall(self.repo)
        self.assertEqual(hook.read_text(), changed)

    def test_doctor(self):
        self.install(claude=True, git_hooks=True)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cg.doctor(self.repo), 0)

    def test_symlink_hook_refused(self):
        target = self.repo / "user-hook"
        target.write_text("#!/bin/sh\nexit 0\n")
        (self.repo / ".git/hooks/pre-commit").symlink_to(target)
        with self.assertRaises(cg.GateError):
            self.install(git_hooks=True)
        self.assertEqual(target.read_text(), "#!/bin/sh\nexit 0\n")

    def test_bad_hook_json_denies(self):
        out = io.StringIO()
        with patch("sys.stdin", io.StringIO("not json")), contextlib.redirect_stdout(out):
            self.assertEqual(cg.claude_hook(self.repo), 0)
        self.assertEqual(json.loads(out.getvalue())["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_claude_exec_hook_fail_closed_configuration(self):
        self.install(claude=True)
        data = json.loads((self.repo / ".claude/settings.local.json").read_text())
        handler = data["hooks"]["PreToolUse"][0]["hooks"][0]
        self.assertEqual(handler["onFailure"], "block")
        self.assertEqual(handler["command"], sys.executable)
        self.assertIn("claude", handler["args"])

    def test_custom_ship_command(self):
        self.write_config([sys.executable, "-c", "raise SystemExit(1)"], extra='ship_commands = ["npm publish"]\n')
        _, text = self.hook("npm publish")
        self.assertEqual(json.loads(text)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_invalid_policy_types_block(self):
        self.write_config(extra='secret_scan = "false"\n')
        self.assertFalse(cg.check(self.repo)["ok"])
        self.write_config(extra='ship_commands = "npm publish"\n')
        self.assertFalse(cg.check(self.repo)["ok"])
        self.write_config(extra='typo_field = true\n')
        self.assertFalse(cg.check(self.repo)["ok"])

    def test_check_log_token_redaction(self):
        token = "AKIA" + "B" * 16
        result = cg.run_command([sys.executable, "-c", "print('AKIA' + 'B' * 16); raise SystemExit(1)"], self.repo, 3)
        self.assertNotIn(token, result["output"])
        self.assertIn("[REDACTED]", result["output"])

    def test_autodetected_python_is_portable(self):
        (self.repo / "pyproject.toml").write_text('[project]\nname="sample"\n')
        (self.repo / "tests").mkdir()
        (self.repo / ".venv/bin").mkdir(parents=True)
        (self.repo / ".venv/bin/python").touch()
        self.assertEqual(cg.detect_checks(self.repo)[0]["command"][0], ".venv/bin/python")

    def test_autodetect_npm(self):
        (self.repo / "package.json").write_text(json.dumps({"scripts": {"test": "vitest run", "lint": "eslint ."}}))
        detected = cg.detect_checks(self.repo)
        self.assertEqual([c["name"] for c in detected], ["lint", "test"])
        self.assertEqual(detected[0]["command"], ["npm", "run", "lint"])

    def test_ignored_generated_files_not_counted(self):
        (self.repo / ".cache").mkdir()
        (self.repo / ".cache/output.txt").write_text("ignored")
        self.assertNotIn(".cache/output.txt", cg.files(self.repo))

    def plugin_hook(self, command, cwd=None):
        payload = {"hook_event_name": "PreToolUse", "cwd": str(cwd or self.repo), "tool_input": {"command": command}}
        out = io.StringIO()
        with patch("sys.stdin", io.StringIO(json.dumps(payload))), contextlib.redirect_stdout(out):
            code = cg.plugin_hook()
        return code, out.getvalue()

    def test_plugin_hook_ignores_repos_without_config(self):
        (self.repo / "codegate.toml").unlink()
        self.assertEqual(self.plugin_hook("git commit -m x"), (0, ""))
        with tempfile.TemporaryDirectory() as outside:
            self.assertEqual(self.plugin_hook("git push", cwd=outside), (0, ""))
        for raw in ("not json", "[]", '{"cwd": 5}'):
            with patch("sys.stdin", io.StringIO(raw)), contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(cg.plugin_hook(), 0)
            self.assertEqual(out.getvalue(), "")

    def test_plugin_hook_requires_local_opt_in(self):
        self.write_config([sys.executable, "-c", "raise SystemExit(1)"])
        self.assertEqual(self.plugin_hook("git push"), (0, ""))

    def test_plugin_hook_gates_opted_in_repo(self):
        self.write_config([sys.executable, "-c", "raise SystemExit(1)"])
        self.install()
        code, out = self.plugin_hook("git push")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["hookSpecificOutput"]["permissionDecision"], "deny")
        (self.repo / "sub").mkdir()
        self.assertIn("deny", self.plugin_hook("git push", cwd=self.repo / "sub")[1])
        self.assertEqual(self.plugin_hook("ls"), (0, ""))
        self.write_config()
        self.assertEqual(self.plugin_hook("git push"), (0, ""))

    def test_plugin_hook_defers_to_local_install(self):
        self.write_config([sys.executable, "-c", "raise SystemExit(1)"])
        self.install(claude=True)
        self.assertEqual(self.plugin_hook("git push"), (0, ""))

    def test_mcp_starts_outside_repository(self):
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "codegate_check", "arguments": {}}},
        ]
        with tempfile.TemporaryDirectory() as outside:
            result = subprocess.run([sys.executable, str(Path(cg.__file__)), "mcp"], cwd=outside, input="\n".join(map(json.dumps, requests)) + "\n", capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        messages = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(messages[0]["result"]["tools"][0]["name"], "codegate_check")
        self.assertIn("Git failed", messages[1]["error"]["message"])

    def test_mcp_path_argument(self):
        def call(arguments, *flags):
            requests = [{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "codegate_check", "arguments": arguments}}]
            with tempfile.TemporaryDirectory() as outside:
                result = subprocess.run([sys.executable, str(Path(cg.__file__)), "mcp", *flags], cwd=outside, input=json.dumps(requests[0]) + "\n", capture_output=True, text=True)
            return json.loads(result.stdout)
        self.assertFalse(call({"path": str(self.repo)}, "--require-path")["result"]["isError"])
        self.assertIn("Pass path", call({}, "--require-path")["error"]["message"])
        self.assertIn("absolute", call({"path": "."})["error"]["message"])
        self.assertIn("Unknown tool", call({"path": str(self.repo), "extra": 1})["error"]["message"])

    def test_plugin_manifests(self):
        root = Path(cg.__file__).resolve().parent
        claude = json.loads((root / ".claude-plugin/plugin.json").read_text())
        codex = json.loads((root / ".codex-plugin/plugin.json").read_text())
        self.assertEqual(claude["version"], cg.VERSION)
        self.assertEqual(codex["version"], cg.VERSION)
        for market in (".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json"):
            self.assertEqual([p["name"] for p in json.loads((root / market).read_text())["plugins"]], ["codegate"])
        handler = json.loads((root / "hooks/hooks.json").read_text())["hooks"]["PreToolUse"][0]["hooks"][0]
        self.assertTrue(handler["command"].endswith("/scripts/codegate\" hook plugin"))
        self.assertTrue(os.access(root / "scripts/codegate", os.X_OK))
        for key in ("skills", "hooks", "mcpServers"):
            self.assertTrue((root / codex[key]).exists(), key)
        for key in ("composerIcon", "logo"):
            self.assertTrue((root / codex["interface"][key]).is_file(), key)
        self.assertEqual((root / "codegate.py").read_bytes(), (root / ".codegate/runner.py").read_bytes())

    def test_plugin_launcher_hook(self):
        root = Path(cg.__file__).resolve().parent
        self.write_config([sys.executable, "-c", "raise SystemExit(1)"])
        self.install()
        payload = json.dumps({"hook_event_name": "PreToolUse", "cwd": str(self.repo), "tool_input": {"command": "git commit -m x"}})
        command = json.loads((root / "hooks/hooks.json").read_text())["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        result = subprocess.run(["sh", "-c", command], input=payload, capture_output=True, text=True, env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(root)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")


if __name__ == "__main__":
    unittest.main()
