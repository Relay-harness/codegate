# CodeGate — public desktop skills edition

CodeGate's setup and check skills run its bundled CLI in a local desktop thread. They inspect the selected Git repository, configure its tests/lint/types, explain gate failures, and can install repository Git pre-commit/pre-push hooks. Requires Python 3.11+, Git, and local command execution with repository access.

Ask “Set up CodeGate in this repository” and review the detected project commands. Then ask “Run CodeGate and explain failing checks.” This public edition declares no MCP server and bundles no agent lifecycle hook. The original repository marketplace distribution and existing private plugin retain their MCP integration.

Configured checks execute with the user's permissions and environment and may modify files or contact services. A pass means the configured checks passed at that time. Use code review and trusted required CI where enforcement must survive local bypass.

Source: https://github.com/Relay-harness/codegate
Support: https://github.com/Relay-harness/codegate/issues
Privacy: https://relay-harness.github.io/codegate/privacy.html
Terms: https://relay-harness.github.io/codegate/terms.html
License: LICENSE

See review/PREPARATION.md for validation and submission state.
