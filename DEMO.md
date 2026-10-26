# Executed live demo

Result: PASS. Full transcript: validation/live-demo.log. Machine-readable outcomes: validation/live-demo-results.json.

Repository: /tmp/codegate-live-demo
Local bare remote: /tmp/codegate-live-demo-remote.git
No network pushes, model calls or changes to existing application repositories were made.

1. Installed actual Claude and Git integrations and checked setup with doctor.
2. Correct addition implementation: actual commit and push passed.
3. Replaced addition with subtraction: syntactically valid Python, but the test failed with -1 != 5.
4. Replayed a documented Claude PreToolUse payload: hook returned permissionDecision deny. This is a protocol simulation, not a live Claude session.
5. Tried an actual git commit: pre-commit blocked it. HEAD was verified unchanged.
6. Fixed the code: actual commit and push passed again.
7. With a clean worktree, deliberately forced a check failure through a demo environment variable: actual pre-push blocked creation of a new remote branch. The remote was checked to confirm the branch did not exist.
8. Removed the forced-failure environment: normal checks were green again.

The demo repo remains in the final passing state. Run its gate again:

```bash
python3.11 /tmp/codegate-live-demo/.codegate/runner.py --repo /tmp/codegate-live-demo check
```

The full CodeGate regression suite also passed: 40 tests. CodeGate enforces defined checks; it does not establish absence of all bugs or resist a user deliberately bypassing local hooks.
