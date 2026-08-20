import ssl
import os
import time
import unittest
from unittest.mock import Mock, patch

from workers import remote_ingestion_worker as worker


PUBLIC_V4 = "93.184.216.34"
PUBLIC_V6 = "2606:4700:4700::1111"


def answer(*addresses):
    return [
        (2 if ":" not in address else 10, 1, 6, "", (address, 443))
        for address in addresses
    ]


class RemoteIngestionSecurityTests(unittest.TestCase):
    def test_public_https_target_allowed_and_canonicalized(self):
        target = worker.validate_target(
            "https://Example.COM/path/data.csv?q=1#ignored",
            resolver=lambda *_args, **_kwargs: answer(PUBLIC_V4),
        )
        self.assertEqual(target.url, "https://example.com/path/data.csv?q=1")
        self.assertEqual(target.addresses, (PUBLIC_V4,))
        self.assertEqual(target.request_target, "/path/data.csv?q=1")

    def test_private_special_and_ipv6_addresses_are_rejected(self):
        blocked = (
            "127.0.0.1",
            "10.0.0.1",
            "172.16.0.1",
            "192.168.0.1",
            "169.254.169.254",
            "100.64.0.1",
            "0.0.0.0",
            "224.0.0.1",
            "::1",
            "fc00::1",
            "fe80::1",
            "::",
            "ff02::1",
            "::ffff:127.0.0.1",
            "::ffff:10.0.0.1",
        )
        for address in blocked:
            with self.subTest(address=address), self.assertRaisesRegex(
                worker.RemoteFetchError, "remote_dns_disallowed"
            ):
                worker.validate_target(
                    "https://example.com/data.csv",
                    resolver=lambda *_args, address=address, **_kwargs: answer(address),
                )

    def test_mixed_public_private_dns_answer_is_rejected(self):
        with self.assertRaisesRegex(worker.RemoteFetchError, "remote_dns_disallowed"):
            worker.validate_target(
                "https://example.com/data.csv",
                resolver=lambda *_args, **_kwargs: answer(PUBLIC_V4, "10.0.0.1"),
            )

    def test_schemes_ports_credentials_and_malformed_urls_are_rejected(self):
        invalid = (
            "http://example.com/data.csv",
            "https://example.com:8443/data.csv",
            "https://user:pass@example.com/data.csv",
            "file:///etc/passwd",
            "ftp://example.com/data.csv",
            "gopher://example.com/data.csv",
            "data:text/plain,test",
            "javascript:alert(1)",
            "//example.com/data.csv",
            "https://example.com/line\nfeed",
        )
        for url in invalid:
            with self.subTest(url=url), self.assertRaisesRegex(
                worker.RemoteFetchError, "remote_url_invalid"
            ):
                worker.validate_target(
                    url, resolver=lambda *_args, **_kwargs: answer(PUBLIC_V4)
                )

    def test_redirect_to_private_redirect_loop_and_limit_are_rejected(self):
        def resolver(host, *_args, **_kwargs):
            return answer("10.0.0.1" if host == "private.example" else PUBLIC_V4)

        with self.assertRaisesRegex(worker.RemoteFetchError, "remote_dns_disallowed"):
            worker.fetch_remote(
                {"url": "https://public.example/a", "tenant_id": "1", "user_id": "2", "request_id": "r"},
                resolver=resolver,
                request_target=lambda *_args, **_kwargs: (
                    302,
                    {"location": "https://private.example/data"},
                    b"",
                ),
            )

        with self.assertRaisesRegex(worker.RemoteFetchError, "remote_redirect_disallowed"):
            worker.fetch_remote(
                {"url": "https://public.example/a", "tenant_id": "1", "user_id": "2", "request_id": "r"},
                resolver=resolver,
                request_target=lambda *_args, **_kwargs: (302, {"location": "/a"}, b""),
            )

        counter = {"value": 0}
        def endless_redirect(target, **_kwargs):
            counter["value"] += 1
            return 302, {"location": f"/next-{counter['value']}"}, b""
        with self.assertRaisesRegex(worker.RemoteFetchError, "remote_redirect_disallowed"):
            worker.fetch_remote(
                {"url": "https://public.example/start", "tenant_id": "1", "user_id": "2", "request_id": "r"},
                resolver=resolver,
                request_target=endless_redirect,
            )
        self.assertEqual(counter["value"], worker.MAX_REDIRECTS + 1)

    def test_dns_rebinding_cannot_change_pinned_connection_and_tls_hostname(self):
        resolver_calls = []
        def rebinding_resolver(*_args, **_kwargs):
            resolver_calls.append(True)
            return answer(PUBLIC_V4 if len(resolver_calls) == 1 else "10.0.0.9")

        target = worker.validate_target(
            "https://data.example/dataset.csv", resolver=rebinding_resolver
        )
        connected = []
        sni = []

        class FakeSocket:
            def settimeout(self, _timeout): pass
            def sendall(self, _value): pass
            def close(self): pass

        class FakeContext:
            verify_mode = ssl.CERT_REQUIRED
            check_hostname = True
            def wrap_socket(self, sock, *, server_hostname):
                sni.append(server_hostname)
                return sock

        class FakeResponse:
            status = 200
            def __init__(self, _socket): self._reads = 0
            def begin(self): pass
            def getheaders(self): return [("Content-Type", "text/csv")]
            def read(self, _size):
                self._reads += 1
                return b"a,b\n1,2\n" if self._reads == 1 else b""
            def close(self): pass

        def connect(address, *, timeout):
            connected.append(address)
            return FakeSocket()

        with patch.object(worker, "HTTPResponse", FakeResponse):
            status, _headers, content = worker._pinned_https_request(
                target,
                deadline=time.monotonic() + 5,
                connection_factory=connect,
                ssl_context=FakeContext(),
            )

        self.assertEqual(status, 200)
        self.assertEqual(content, b"a,b\n1,2\n")
        self.assertEqual(connected, [(PUBLIC_V4, 443)])
        self.assertEqual(sni, ["data.example"])
        self.assertEqual(len(resolver_calls), 1)

    def test_tls_verification_cannot_be_disabled(self):
        target = worker.ValidatedTarget(
            url="https://example.com/",
            hostname="example.com",
            port=443,
            request_target="/",
            addresses=(PUBLIC_V4,),
        )
        insecure = Mock(verify_mode=ssl.CERT_NONE, check_hostname=False)
        raw = Mock()
        with self.assertRaisesRegex(worker.RemoteFetchError, "remote_tls_error"):
            worker._pinned_https_request(
                target,
                deadline=time.monotonic() + 5,
                connection_factory=lambda *_args, **_kwargs: raw,
                ssl_context=insecure,
            )

    def test_encoded_and_plain_oversized_responses_are_rejected(self):
        target = worker.ValidatedTarget(
            url="https://example.com/", hostname="example.com", port=443,
            request_target="/", addresses=(PUBLIC_V4,)
        )
        class FakeSocket:
            def settimeout(self, _timeout): pass
            def sendall(self, _value): pass
            def close(self): pass
        class FakeContext:
            verify_mode = ssl.CERT_REQUIRED
            check_hostname = True
            def wrap_socket(self, sock, *, server_hostname): return sock
        class EncodedResponse:
            status = 200
            def __init__(self, _socket): pass
            def begin(self): pass
            def getheaders(self): return [("Content-Encoding", "gzip")]
            def close(self): pass
        with patch.object(worker, "HTTPResponse", EncodedResponse), self.assertRaisesRegex(
            worker.RemoteFetchError, "remote_content_invalid"
        ):
            worker._pinned_https_request(
                target, deadline=time.monotonic() + 5,
                connection_factory=lambda *_args, **_kwargs: FakeSocket(),
                ssl_context=FakeContext(),
            )

        class LargeResponse(EncodedResponse):
            def getheaders(self): return [("Content-Length", str(worker.MAX_REMOTE_BYTES + 1))]
        with patch.object(worker, "HTTPResponse", LargeResponse), self.assertRaisesRegex(
            worker.RemoteFetchError, "remote_too_large"
        ):
            worker._pinned_https_request(
                target, deadline=time.monotonic() + 5,
                connection_factory=lambda *_args, **_kwargs: FakeSocket(),
                ssl_context=FakeContext(),
            )

    def test_overall_deadline_and_request_contract_are_enforced(self):
        with self.assertRaisesRegex(worker.RemoteFetchError, "remote_timeout"):
            worker.fetch_remote(
                {"url": "https://example.com/a", "tenant_id": "1", "user_id": "2", "request_id": "r"},
                resolver=lambda *_args, **_kwargs: answer(PUBLIC_V4),
                request_target=lambda *_args, **_kwargs: (_ for _ in ()).throw(worker.RemoteFetchError("remote_timeout")),
            )
        for extra in ({"headers": {}}, {"method": "POST"}, {"body": "x"}, {"proxy": "x"}):
            with self.subTest(extra=extra), self.assertRaisesRegex(
                worker.RemoteFetchError, "remote_request_invalid"
            ):
                worker.fetch_remote(
                    {"url": "https://example.com/a", "tenant_id": "1", "user_id": "2", "request_id": "r", **extra},
                    resolver=lambda *_args, **_kwargs: answer(PUBLIC_V4),
                )

    def test_compose_isolates_and_constrains_egress_worker(self):
        from pathlib import Path
        repository_root = Path(
            os.getenv("MADAR_TEST_REPOSITORY_ROOT", Path(__file__).resolve().parents[2])
        )
        compose = (repository_root / "docker-compose.yml").read_text(encoding="utf-8")
        service = compose.split("\n  remote-ingestion-worker:\n", 1)[1].split("\n  frontend:\n", 1)[0]
        self.assertIn('user: "65534:65534"', service)
        self.assertIn("read_only: true", service)
        self.assertIn('cap_drop: ["ALL"]', service)
        self.assertIn('security_opt: ["no-new-privileges:true"]', service)
        self.assertIn("pids_limit: 32", service)
        self.assertIn("- remote_ingestion_internal", service)
        self.assertIn("- remote_ingestion_egress", service)
        self.assertNotIn("env_file:", service)
        self.assertNotIn("volumes:", service)
        self.assertNotIn("ports:", service)
        networks = compose.split("\nnetworks:\n", 1)[1]
        self.assertIn("remote_ingestion_internal:\n    internal: true", networks)


if __name__ == "__main__":
    unittest.main()
