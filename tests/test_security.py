from pathlib import Path
import tempfile
import unittest

from stupidex.security import safe_path, validate_command

class SecurityTests(unittest.TestCase):
    def test_path_inside_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.assertEqual(safe_path(root,"src/app.py"), (root/"src/app.py").resolve())
    def test_path_traversal_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PermissionError):
                safe_path(Path(tmp),"../secret")
    def test_shell_operators_blocked(self):
        for command in ("pytest | cat","git status && env","python x.py > out"):
            with self.assertRaises(PermissionError):
                validate_command(command)
    def test_inline_code_blocked(self):
        with self.assertRaises(PermissionError):
            validate_command("python -c print(1)")
    def test_safe_commands(self):
        self.assertEqual(validate_command("pytest -q"), ["pytest","-q"])
        self.assertEqual(validate_command("git status --short"), ["git","status","--short"])

if __name__ == "__main__": unittest.main()
