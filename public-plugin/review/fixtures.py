"""Create disposable, dependency-free review repositories; never touch an existing path."""
from pathlib import Path
import argparse
import json
import subprocess
import sys


def create(destination):
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    for name in ("pass", "fail", "syntax", "no-config", "path with spaces"):
        repo = destination / name
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / ".gitignore").write_text("__pycache__/\n*.pyc\n")
        (repo / "app.py").write_text("def add(a, b):\n    return a + b\n")
        (repo / "test_app.py").write_text(
            "import unittest\nfrom app import add\n\n"
            "class AddTests(unittest.TestCase):\n"
            f"    def test_add(self):\n        self.assertEqual(add(2, 3), {6 if name == 'fail' else 5})\n"
        )
        if name == "syntax":
            (repo / "app.py").write_text("def add(a, b)\n    return a + b\n")
        if name != "no-config":
            command = [sys.executable, "-m", "unittest", "discover", "-v"]
            (repo / "codegate.toml").write_text(
                "version = 1\ntimeout = 30\npython_syntax = true\n"
                "[[checks]]\nname = \"unit tests\"\n"
                + "command = " + json.dumps(command) + "\ntimeout = 10\n"
            )
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(create(args.destination))
