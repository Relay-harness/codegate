# CodeGate public submission

Version 0.2.0 is a desktop-only skills package. It invokes the bundled CLI directly and does not declare an MCP server. The original marketplace/private MCP integration remains in the main project.

The publisher selected the Personal OpenAI organization, verified the Individual identity Sathwik R, chose all available countries and confirmed that CodeGate has no commerce. CodeGate-specific privacy and terms pages are published and verified. GitHub-only support and the published privacy contact were confirmed by the creator.

The preceding 0.1.2 MCP draft was uploaded and both skills passed scans, but the portal blocked its command MCP configuration. The 0.2.0 package implements the documented desktop-only skills path instead of declaring a local MCP server. After reupload, inspect the saved package inventory and scans; report any remaining platform restriction rather than bypassing it.

The setup skill creates codegate.toml, vendors the runner and can install repository Git hooks. The check skill invokes the bundled launcher with the absolute repository path and reports the actual result. Local checks run with user permissions, not in a sandbox. No server connection, MCP test cases or MCP demonstration recording applies to this skills-only package. A live desktop installation must still be validated where available.

Submission requires completed package/skill checks and the developer's legal/policy attestations. Do not accept attestations for the user or claim publication before an approved release is published. Portal status must be verified after upload.

References:
- https://developers.openai.com/plugins/deploy/desktop-only
- https://developers.openai.com/plugins/deploy/submission
