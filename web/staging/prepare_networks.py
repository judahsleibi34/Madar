#!/usr/bin/env python3
"""Create and attest isolated staging slot networks with explicit CIDRs."""

from __future__ import annotations

import ipaddress
import json
import subprocess


NETWORKS = {
    "madar-stage-blue-default": ("10.251.0.0/24", False, "blue"),
    "madar-stage-blue-parser-internal": ("10.251.1.0/24", True, "blue"),
    "madar-stage-blue-remote-egress": ("10.251.2.0/24", False, "blue"),
    "madar-stage-blue-remote-internal": ("10.251.3.0/24", True, "blue"),
    "madar-stage-green-default": ("10.251.4.0/24", False, "green"),
    "madar-stage-green-parser-internal": ("10.251.5.0/24", True, "green"),
    "madar-stage-green-remote-egress": ("10.251.6.0/24", False, "green"),
    "madar-stage-green-remote-internal": ("10.251.7.0/24", True, "green"),
}


def inspect(name: str) -> dict | None:
    completed = subprocess.run(
        ["docker", "network", "inspect", name], text=True,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    if completed.returncode:
        return None
    rows = json.loads(completed.stdout)
    return rows[0] if len(rows) == 1 else None


def validate(name: str, expected_cidr: str, internal: bool, slot: str) -> None:
    row = inspect(name)
    if row is None:
        command = [
            "docker", "network", "create", "--driver", "bridge",
            "--subnet", expected_cidr,
            "--label", "com.madar.scope=staging",
            "--label", f"com.madar.slot={slot}",
        ]
        if internal:
            command.append("--internal")
        subprocess.run([*command, name], check=True, stdout=subprocess.DEVNULL)
        row = inspect(name)
    if row is None:
        raise RuntimeError(f"staging network unavailable: {name}")
    actual = {
        str(ipaddress.ip_network(config["Subnet"]))
        for config in row.get("IPAM", {}).get("Config", []) if config.get("Subnet")
    }
    labels = row.get("Labels") or {}
    if actual != {expected_cidr} or bool(row.get("Internal")) is not internal:
        raise RuntimeError(f"staging network configuration mismatch: {name}")
    if labels.get("com.madar.scope") != "staging" or labels.get("com.madar.slot") != slot:
        raise RuntimeError(f"staging network ownership labels mismatch: {name}")


def main() -> int:
    for name, (cidr, internal, slot) in NETWORKS.items():
        validate(name, cidr, internal, slot)
    print(f"PASS: {len(NETWORKS)} isolated staging networks attested")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
