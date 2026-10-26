# Contributing to CodeGate

Thanks for contributing. By submitting a contribution, you agree it can be distributed under the repository MIT license.

1. Open an issue first for significant behavior or policy changes. Do not include private credentials, customer data, or vulnerability details in public issues.
2. Fork the repository and make a focused change with tests. Use Python 3.11+ on macOS or Linux.
3. Create a Python 3.11+ environment with `python3 -m venv .venv` (using a Python 3.11+ binary), then run `.venv/bin/python -m unittest discover -s tests -v` and `.venv/bin/python codegate.py check` before submitting a pull request. The test suite uses temporary local repositories and a local bare remote.
4. Describe what changed, how you tested it, and any known limits in the pull request. Update the documentation for user-visible behavior.

The maintainers review contributions as time allows. No response time or acceptance is guaranteed. Please follow the [Code of Conduct](CODE_OF_CONDUCT.md). Security issues belong in the [private reporting channel](SECURITY.md), not a public pull request.
