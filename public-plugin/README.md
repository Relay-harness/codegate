# CodeGate — directory edition (draft)

Run a local Git repository's configured tests, lint and type checks and report why a gate failed. Requires Python 3.11+, Git, and a local desktop Codex thread with access to the repository. This free, MIT-licensed plugin requires no API key or account.

Ask “Set up CodeGate in this repository” to create codegate.toml, vendor the runner, and install repository-local Git pre-commit/pre-push hooks. Review the detected project commands before running them. Ask “Run CodeGate and explain failing checks” to use the codegate_check tool with the repository's absolute path.

This directory edition excludes bundled agent lifecycle hooks. Git hooks must be installed per repository. Local checks are not a sandbox; configured commands can change files or access the network. A pass establishes only that the configured checks passed. Use trusted required CI for enforcement against bypass.

Source: https://github.com/Relay-harness/codegate
Support: https://github.com/Relay-harness/codegate/issues
License: LICENSE

Public submission is incomplete: deployment and verification of the dedicated CodeGate privacy/terms pages, a verified desktop recording, target-host checks, and final portal checks/attestations remain. Local MCP eligibility was confirmed by the creator and must be verified for the submitting organization in the portal. See review/PREPARATION.md.
