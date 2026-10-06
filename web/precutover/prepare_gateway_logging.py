"""Prepare a new gateway template; never overwrite the installed template."""
import argparse
import hashlib
import os
from pathlib import Path


def safe_template(text: str) -> str:
    path = '%REQ(X-ENVOY-ORIGINAL-PATH?:PATH)%'
    referer = '%REQ(REFERER)%'
    if text.count(path) != 1 or text.count(referer) != 1:
        raise ValueError('gateway_log_template_requires_review')
    # Envoy PATH(NQ) explicitly excludes queries. Do not retain Referer URLs.
    return text.replace(path, '%PATH(NQ:ORIG_OR_PATH)%').replace(referer, '-')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-sha256', required=True)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.expected_sha256:
        raise SystemExit('gateway template checksum mismatch; stop for review')
    result = safe_template(raw.decode())
    os.umask(0o077)
    with args.output.open('x') as output:
        output.write(result)


if __name__ == '__main__':
    main()
