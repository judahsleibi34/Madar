"""Prevent security regressions from silently falling outside the CI runner."""

import ast
from pathlib import Path
import unittest


class TestDiscoveryContractTests(unittest.TestCase):
    def test_ci_modules_do_not_contain_uncollected_function_tests(self):
        missed = []
        for path in sorted(Path(__file__).parent.glob("test_*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            functions = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
            if any(node.name == "load_tests" for node in functions):
                continue  # A module may explicitly integrate with unittest.
            missed.extend(f"{path.name}:{node.lineno}:{node.name}" for node in functions if node.name.startswith("test_"))
        self.assertEqual(missed, [], "Convert function tests to unittest.TestCase or supply load_tests")
