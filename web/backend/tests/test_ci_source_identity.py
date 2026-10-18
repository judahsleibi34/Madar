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
                self.assertIn("codex/outbox-claim-fencing-20261017", source)
                self.assertIn("CI_SOURCE_SHA: " + SOURCE, source)
                self.assertIn("          ref: " + SOURCE, source)
                self.assertIn("          persist-credentials: false", source)
                self.assertEqual(self.run_guard(name, self.head), 0)

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
        self.assertIn("branches: [main,", source)
        self.assertIn("codex/integration-review-20261017", source)
        self.assertIn("codex/outbox-claim-fencing-20261017", source)
        self.assertNotIn("    paths:", source)
        self.assertNotIn("    paths-ignore:", source)


if __name__ == "__main__":
    unittest.main()
