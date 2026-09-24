import os
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request

from services.hosted_address_service import (
    enforce_request_tenant_identity,
    hosted_tenant_from_hostname,
    request_hosted_tenant,
    RESERVED_HOSTED_NAMES,
    validate_hosted_address,
)


def request_for(host, forwarded_host="", client="127.0.0.1"):
    headers = [(b"host", host.encode())]
    if forwarded_host:
        headers.append((b"x-forwarded-host", forwarded_host.encode()))
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/public/sites/acme",
        "headers": headers,
        "client": (client, 1234),
        "scheme": "https",
        "server": (host, 443),
    })


class HostedAddressServiceTests(unittest.TestCase):
    def test_reserved_name_contract_is_enforced_by_migration(self):
        candidates = (
            Path(__file__).resolve().parents[2] / "database/migrations/105_canonical_tenant_subdomains.sql",
            Path(__file__).resolve().parents[1] / "database/migrations/105_canonical_tenant_subdomains.sql",
        )
        migration_path = next(path for path in candidates if path.is_file())
        migration = migration_path.read_text()
        for label in RESERVED_HOSTED_NAMES:
            self.assertIn(f"'{label}'", migration)

    def test_hostname_classification_contract(self):
        cases = {
            "acme.madarportal.com": "acme",
            "ACME.madarportal.com": "acme",
            "acme.madarportal.com.": "acme",
            "madarportal.com": "",
            "www.madarportal.com": "",
            "api.madarportal.com": "",
            "evil-madarportal.com": "",
            "acme.madarportal.com.evil.com": "",
            "invalid..madarportal.com": "",
            "-invalid.madarportal.com": "",
            "invalid-.madarportal.com": "",
        }
        with patch.dict(os.environ, {"PUBLIC_SITE_DOMAIN": "madarportal.com"}):
            for hostname, expected in cases.items():
                with self.subTest(hostname=hostname):
                    self.assertEqual(hosted_tenant_from_hostname(hostname), expected)

    def test_host_and_path_identity_must_agree(self):
        with patch.dict(os.environ, {"PUBLIC_SITE_DOMAIN": "madarportal.com"}):
            request = request_for("tenant-a.madarportal.com")
            self.assertEqual(enforce_request_tenant_identity(request, "tenant-a"), "tenant-a")
            with self.assertRaises(HTTPException) as caught:
                enforce_request_tenant_identity(request, "tenant-b")
            self.assertEqual(caught.exception.status_code, 404)

    def test_invalid_public_domain_host_fails_closed(self):
        with patch.dict(os.environ, {"PUBLIC_SITE_DOMAIN": "madarportal.com"}):
            for hostname in (
                "invalid..madarportal.com",
                "acme.madarportal.com:not-a-port",
                "attacker@acme.madarportal.com",
            ):
                with self.subTest(hostname=hostname), self.assertRaises(HTTPException) as caught:
                    request_hosted_tenant(request_for(hostname))
                self.assertEqual(caught.exception.status_code, 400)

    def test_reserved_infrastructure_host_is_not_a_tenant(self):
        with patch.dict(os.environ, {"PUBLIC_SITE_DOMAIN": "madarportal.com"}):
            self.assertEqual(request_hosted_tenant(request_for("api.madarportal.com")), "")

    def test_reserved_infrastructure_names_cannot_be_assigned(self):
        for label in ("api", "admin", "www", "mail"):
            with self.subTest(label=label), self.assertRaises(HTTPException) as caught:
                validate_hosted_address(label)
            self.assertEqual(caught.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
