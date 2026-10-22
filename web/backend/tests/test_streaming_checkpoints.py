import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from services import checkpoint_streaming


class StreamingCheckpointScratchTests(unittest.TestCase):
    def test_stale_worker_scratch_is_cleaned_without_touching_fresh_or_foreign_paths(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {
            "DATA_CHECKPOINT_SCRATCH_DIR": root,
        }, clear=False):
            scratch = Path(root)
            stale = scratch / "checkpoint-stale"
            fresh = scratch / "checkpoint-fresh"
            foreign = scratch / "keep-me"
            for path in (stale, fresh, foreign):
                path.mkdir()
                (path / "evidence").write_text("private", encoding="utf-8")
            old = time.time() - checkpoint_streaming.STALE_SCRATCH_SECONDS - 10
            os.utime(stale, (old, old))

            removed = checkpoint_streaming.cleanup_stale_workspaces()

            self.assertEqual(removed, 1)
            self.assertFalse(stale.exists())
            self.assertTrue(fresh.exists())
            self.assertTrue(foreign.exists())

    def test_workspace_is_private_and_cleanup_is_scoped(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {
            "DATA_CHECKPOINT_SCRATCH_DIR": root,
        }, clear=False):
            workspace = checkpoint_streaming.create_workspace(
                "11111111-1111-4111-8111-111111111111",
            )
            self.assertEqual(workspace.stat().st_mode & 0o777, 0o700)
            artifact_path = workspace / "artifact"
            artifact_path.write_bytes(b"private")
            artifact = checkpoint_streaming.ReconstructionArtifact(
                workspace=workspace, csv_path=artifact_path, record_count=0,
                change_count=0, state_hash="a" * 64, checkpoint_sha256="b" * 64,
                checkpoint_size_bytes=7, resource_key="test",
                latest_committed_revision=1, database_reads=0, database_writes=0,
                immutable_bytes_read=0,
            )
            artifact.cleanup()
            self.assertFalse(workspace.exists())
            self.assertTrue(Path(root).exists())


if __name__ == "__main__":
    unittest.main()
