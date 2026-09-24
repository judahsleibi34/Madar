import os
import unittest
from unittest import mock

from routes import health_routes


class HealthReleaseIdentityTests(unittest.TestCase):
    def test_version_exposes_exact_controlled_release_identity(self):
        environment = {
            "MADAR_RELEASE_SHA": "a" * 40,
            "MADAR_RELEASE_SLOT": "blue",
            "MADAR_BUILD_TIMESTAMP": "2026-09-24T12:00:00Z",
            "SCHEMA_COMPATIBLE_MIN": "81",
            "SCHEMA_COMPATIBLE_MAX": "105",
        }

        with mock.patch.dict(os.environ, environment, clear=False):
            identity = health_routes.version()

        self.assertEqual(identity["release_sha"], "a" * 40)
        self.assertEqual(identity["release_slot"], "blue")
        self.assertEqual(
            identity["build_timestamp"],
            "2026-09-24T12:00:00Z",
        )
        self.assertEqual(identity["schema_compatible_min"], 81)
        self.assertEqual(identity["schema_compatible_max"], 105)

    def test_version_does_not_invent_a_release_slot(self):
        environment = {
            "MADAR_RELEASE_SHA": "development",
            "MADAR_BUILD_TIMESTAMP": "unknown",
            "SCHEMA_COMPATIBLE_MIN": "81",
            "SCHEMA_COMPATIBLE_MAX": "105",
        }

        with mock.patch.dict(
            os.environ,
            environment,
            clear=False,
        ):
            os.environ.pop("MADAR_RELEASE_SLOT", None)
            identity = health_routes.version()

        self.assertEqual(identity["release_slot"], "")


if __name__ == "__main__":
    unittest.main()
