# Public submission preparation

Status: draft only; not uploaded, submitted, approved, or public.

Creator-confirmed publication choices: free with no purchases, all available countries, and local-MCP submission approval already obtained. The saved plugin's publisher name is Sathwik R; the exact verified organization and identity still need to be checked in the portal.

This separate directory edition excludes bundled agent lifecycle hooks. Repository Git hooks remain available through explicit setup. The existing private plugin and GitHub release remain unaffected.

## Listing draft

CodeGate — Checks before code ships. Developer Tools. Runs configured local repository tests, lint and types and explains failures. Requires Python 3.11+, Git and a local desktop thread. Commands run with the user's permissions; a passing result is not proof of bug-free code.

CodeGate uses its own dedicated privacy and terms pages at docs/privacy.html and docs/terms.html in this repository. They describe the local runner, MCP output, GitHub-hosted support, and MIT license. The creator confirmed GitHub-only support and approved sathwik07@scriptonia.dev as the published privacy contact. Both pages are deployed and were verified with HTTP 200 responses, the correct CodeGate content and the confirmed privacy contact. The root and compatibility manifests use these CodeGate URLs.

## Remaining steps, in order

1. Install this exact directory edition in a local desktop thread. Verify setup, Git hooks, and actual MCP use. The private plugin currently installed is a different edition.
2. Record the desktop walkthrough below, host it at an accessible link, play it back, then set review.demo_recording_url. The script below is not a recording.
3. Rebuild and inspect the final ZIP. Select the intended verified organization and publisher in the submission portal, confirm local-MCP eligibility, and upload the draft. Inspect imported metadata and run applicable cases against that saved version.
4. The authorized developer completes the portal's legal/policy attestations and any required scans. Submit for review. Publish only after approval.

The available account plugin tools create/update private plugins; they do not submit or publish a public listing. The originating local browser connection was unavailable in this session, and no video-recording tool was exposed. GitHub access is now connected for source publication.

## Review cases

Five positive cases are embedded in plugin.json: passing unittest suite, actual assertion failure, invalid Python syntax, missing configuration with setup recovery, and an absolute repository path containing spaces. Three negative cases cover unsupported deployment, nonexistent paid subscriptions, and organization-wide GitHub access without a local checkout. These are draft cases for correction; target-host conversational review remains unrun.

Generate disposable sample repositories with Python 3.11+:

```sh
python3 review/fixtures.py /absolute/new/fixture-directory
```

The destination must not already exist. Replace `<FIXTURES>` in the review cases with the generated absolute path. Fixtures use only Python's standard library and do not contact services. Do not include their generated .git directories in the plugin archive.

## Desktop recording walkthrough

Record a dedicated test thread with no production data, credentials or private files visible. Show the directory edition's version and setup in a disposable Git repository. Ask “Set up CodeGate in this repository,” review its detected command, and show the installed Git hooks. Then ask to run the passing fixture, show the real codegate_check call and PASS output, run the failing fixture and show BLOCKED with the assertion, and try no-config to show an honest setup error. Ask to deploy to Vercel and show the capability limit without an invented success. Keep tool results readable, stop recording, and verify playback before sharing the hosted link.

For the demo, an accessible local desktop setup is required. Browser screenshots and terminal fixtures do not prove the actual ChatGPT/Codex integration works. A terminal test log cannot substitute for the recording.

## Public-directory references

- https://developers.openai.com/plugins/deploy/desktop-only — local MCP eligibility and desktop-only distribution.
- https://developers.openai.com/plugins/deploy/submission — bundled lifecycle hooks are ineligible; upload, review and publication are separate.

The source includes five positive and three negative review cases, release notes, explicit free-commerce metadata and unrestricted country targeting. No placeholder policy or video URL and no unsupported legal attestation has been inserted.

## Verified CodeGate policy URLs

- Privacy: https://relay-harness.github.io/codegate/privacy.html
- Terms: https://relay-harness.github.io/codegate/terms.html

No Relay policy is used. Both pages were verified after successful GitHub Pages deployment.
