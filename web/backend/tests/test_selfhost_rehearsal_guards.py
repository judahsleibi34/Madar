import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = next(p for p in [Path("/scripts/prepare_selfhost_rehearsal.py"), Path(__file__).resolve().parents[2] / "scripts/prepare_selfhost_rehearsal.py"] if p.is_file())
spec = importlib.util.spec_from_file_location("selfhost_rehearsal", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RehearsalGuardTests(unittest.TestCase):
    def fixture(self):
        original = {"name": "supabase", "services": {name: {"image": "example/test:1", "environment": {}, "volumes": ["./volumes/test:/data"], "ports": ["0.0.0.0:5432:5432"]} for name in module.SERVICES}}
        original["services"]["functions"] = {"image": "unused"}
        lock = {"commit": module.UPSTREAM_SHA, "images": [{"image": "example/test:1", "digest": "sha256:" + "a" * 64, "status": "resolved"}]}
        return original, lock

    def test_refuses_production_and_existing_targets(self):
        for path in ["/srv/madar/production/selfhost-rehearsal", "/srv/data1/selfhost-rehearsal", "/srv/data2/docker/selfhost-rehearsal", "/etc/madar/selfhost-rehearsal", "relative/selfhost-rehearsal", "/tmp/../srv/selfhost-rehearsal"]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                module.validate_target(Path(path))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "selfhost-rehearsal"
            module.validate_target(target)
            target.mkdir()
            with self.assertRaises(ValueError): module.validate_target(target)

    def test_refuses_symlink_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); (root/"link").symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError): module.validate_target(root/"link/selfhost-rehearsal")

    def test_no_provider_credentials_inherited_by_compose(self):
        with patch.dict(os.environ, {"POSTGRES_PASSWORD": "do-not-copy", "SUPABASE_SECRET_KEY": "do-not-copy", "DOCKER_HOST": "tcp://other:2375"}):
            actual=module.clean_environment()
        self.assertNotIn("POSTGRES_PASSWORD",actual)
        self.assertNotIn("SUPABASE_SECRET_KEY",actual)
        self.assertNotIn("DOCKER_HOST",actual)

    def test_every_published_port_is_loopback_and_images_are_immutable(self):
        original,lock=self.fixture(); result=module.isolated_compose(original,lock)
        self.assertNotIn("functions",result["services"])
        for service in result["services"].values():
            self.assertIn("@sha256:",service["image"])
            self.assertEqual(service["restart"],"no")
            for port in service.get("ports",[]): self.assertTrue(port.startswith("127.0.0.1:554"))
        self.assertNotEqual(result["name"],original["name"])
        self.assertEqual(original["services"]["db"]["ports"],["0.0.0.0:5432:5432"])

    def test_missing_or_mutable_digest_is_refused(self):
        for digest in ["latest", "", "sha256:bad"]:
            original,lock=self.fixture(); lock["images"][0]["digest"]=digest
            with self.assertRaises(ValueError): module.isolated_compose(original,lock)

    def test_production_bind_and_parent_escape_are_refused(self):
        for mount in ["/srv/madar/production:/app", "./volumes/../../production:/data", "/srv/data2/docker:/data", "docker.sock:/var/run/docker.sock"]:
            original,lock=self.fixture(); original["services"]["db"]["volumes"]=[mount]
            with self.assertRaises(ValueError): module.isolated_compose(original,lock)

    def test_host_network_and_privileged_service_are_refused(self):
        for key,value in [("network_mode","host"),("privileged",True),("devices",["/dev/sdc"])]:
            original,lock=self.fixture(); original["services"]["db"][key]=value
            with self.assertRaises(ValueError): module.isolated_compose(original,lock)

    def test_wrong_upstream_and_missing_service_are_refused(self):
        original,lock=self.fixture(); lock["commit"]="b"*40
        with self.assertRaises(ValueError): module.isolated_compose(original,lock)
        original,lock=self.fixture(); del original["services"]["auth"]
        with self.assertRaises(ValueError): module.isolated_compose(original,lock)
