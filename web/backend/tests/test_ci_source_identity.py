"""Exercise the actual CI source guard against head/merge and dirty-tree drift."""
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(os.getenv("MADAR_TEST_REPOSITORY_ROOT") or Path(__file__).resolve().parents[3])
WORKFLOWS = ROOT / ".github" / "workflows"
SOURCE = "${{ github.event.pull_request.head.sha || github.sha }}"


def guard(workflow):
    lines = workflow.read_text().splitlines()
    start = lines.index("      - name: Verify exact clean source")
    if lines[start + 1] != "        run: |":
        raise AssertionError("Source verification must execute before build/test steps")
    end = next((i for i in range(start + 2, len(lines)) if lines[i].startswith("      - name:")), len(lines))
    return textwrap.dedent("\n".join(lines[start + 2:end])).strip()


class CiSourceIdentityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repository = Path(temporary.name)
        self.git("init", "--quiet")
        (self.repository / "source").write_text("reviewed PR head\n")
        self.git("add", "source")
        self.git("-c", "user.name=Saliba Rishmawi", "-c",
                 "user.email=75858844+Saliba-codes@users.noreply.github.com",
                 "commit", "--quiet", "-m", "synthetic exact-source fixture")
        self.head = self.git("rev-parse", "HEAD").strip()

    def git(self, *arguments):
        return subprocess.check_output(["git", *arguments], cwd=self.repository, text=True)

    def run_guard(self, name, sha):
        return subprocess.run(["bash", "-e", "-c", guard(WORKFLOWS / name)],
                              cwd=self.repository, env={**os.environ, "CI_SOURCE_SHA": sha},
                              capture_output=True, text=True).returncode

    def test_workflows_bind_checkout_and_guard_to_the_same_reviewed_head(self):
        for name in ("backend-check.yml", "frontend-check.yml"):
            with self.subTest(workflow=name):
                source = (WORKFLOWS / name).read_text()
                self.assertIn("  pull_request: {}", source)
                self.assertIn("CI_SOURCE_SHA: " + SOURCE, source)
                self.assertIn("          ref: " + SOURCE, source)
                self.assertIn("          persist-credentials: false", source)
                self.assertEqual(self.run_guard(name, self.head), 0)

    def test_phase6_base_runs_all_required_source_checks(self):
        for name in ('backend-check.yml', 'frontend-check.yml', 'schema148-artifacts.yml'):
            self.assertIn('  pull_request: {}', (WORKFLOWS/name).read_text())

    def test_phase7_base_runs_all_required_checks_and_real_inventory(self):
        for name in ('backend-check.yml', 'frontend-check.yml', 'schema148-artifacts.yml'):
            self.assertIn('  pull_request: {}', (WORKFLOWS/name).read_text())
        self.assertIn('python3 web/scripts/check_privileged_inventory.py',
                      (WORKFLOWS/'backend-check.yml').read_text())

    def test_generic_migration_workflow_is_always_read_only_and_exact_source(self):
        source=(WORKFLOWS/'migration-safety.yml').read_text()
        for required in ('  pull_request: {}','contents: read','persist-credentials: false',
                         'fetch-depth: 0','CI_HISTORY_BASE_SHA:','web/scripts/validate_migration_candidate.py',
                         'web/scripts/rehearse_generic_migrations.sh', 'timeout-minutes: 30'):
            self.assertIn(required,source)
        for forbidden in ('pull_request_target:', 'secrets.', 'self-hosted', 'production-deploy',
                          'write-all', 'permissions: write', '    paths:', '    paths-ignore:'):
            self.assertNotIn(forbidden,source)

    def test_guard_rejects_a_different_merge_tree(self):
        for name in ("backend-check.yml", "frontend-check.yml"):
            with self.subTest(workflow=name):
                self.assertNotEqual(self.run_guard(name, "0" * 40), 0)

    def test_guard_rejects_tracked_and_untracked_mutation(self):
        for relative in ("source", "untracked"):
            (self.repository / relative).write_text("substituted source\n")
            for name in ("backend-check.yml", "frontend-check.yml"):
                with self.subTest(workflow=name, mutation=relative):
                    self.assertNotEqual(self.run_guard(name, self.head), 0)
            if relative == "source":
                self.git("checkout", "--", "source")

    def test_candidate_check_covers_main_without_path_condition(self):
        source = (WORKFLOWS / "schema148-artifacts.yml").read_text()
        self.assertIn("  pull_request: {}", source)
        self.assertNotIn("    branches:", source)
        self.assertNotIn("    paths:", source)
        self.assertNotIn("    paths-ignore:", source)


if __name__ == "__main__":
    unittest.main()
