# Validation

Tested on macOS arm64 with Python 3.13.17 and local Git.

## Automated results

`python -m unittest discover -s tests -v`: **48 tests passed** (Linux, Python 3.13, after the plugin packaging change; the original 40-test run was on macOS).

Coverage includes:
- Missing/invalid/empty policies block instead of passing.
- Declared check failure, absent binary, syntax error and obvious credential detection.
- Output-token redaction for supported patterns; timeout/output bounds.
- Source mutation invalidates a passing command.
- Staged/worktree alignment and untracked-file rules.
- Claude documented hook deny/no-decision behavior, malformed input and optional Stop feedback.
- Local settings merge/idempotence and preserving unrelated later edits.
- Existing executable hooks restored/chained; prior failure propagates.
- Modified wrapper and symlink hook safety; custom hooksPath refused.
- Actual Git commits pass/block, and pushes to a temporary local bare remote pass/block.
- Non-HEAD refs are refused.
- MCP initialize/tools/list/tools/call round trip.
- MCP server starting outside a repository, and `path` argument validation.
- Plugin hook: pass-through outside Git, without `codegate.toml`, and without a local install receipt (cloned policy alone); gating opted-in repositories (including subdirectories), deferring to a project-local hook, and running the shipped `hooks/hooks.json` command through `sh`.
- Plugin manifest consistency: versions, referenced files, executable launcher and identical vendored runner.
- Portable Python executable detection, Node script discovery and doctor diagnostics.

Full output is in `validation/test-output.txt`. The checks do not call a model or push to a network remote.

## Packaging

`uv build` produced a wheel and source archive. Runtime has no third-party dependencies. The build backend is hatchling; installing from source may download build tooling. This has not been published to PyPI or an assistant marketplace.

## Plugins

`claude plugin validate .` passes for the Claude Code plugin and marketplace. The plugins have not been installed into a live Claude Code or Codex session yet. The Codex manifest follows the documented `.codex-plugin` format, but it is not machine-validated.

## Not yet certified

Live Claude Code/Desktop/Codex onboarding, Windows, Linux execution, external CI execution, real Node project integration, all framework variants, hostile-command bypass resistance and production security certification. Claude hook and MCP protocol tests use documented payloads. A packaged GitHub Actions example is a template, not an executed hosted workflow.

PASS means the configured checks passed under the documented bounds, not that code has no bugs. See README and DESIGN for enforcement boundaries.
