"""Governed GoTrue-only Gmail/callback configuration before normal graduation.

This preparation operation never authorizes traffic, workers or business writes.
It requires the existing Phase-2 recovery credential and final migration proofs.
The subsequent normal authorization still requires every gate, including SMTP.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import smtplib
import ssl
import time

from deployment.lib.environment_file import load_environment_file
from deployment.lib.provider_local_transition import GATES
from deployment.lib.provider_recovery_bootstrap import exclusive_lock
from deployment.lib.provider_recovery_runtime import digest, protected, readonly_configuration
from deployment.lib.release_deployer import atomic_json

NATIVE = Path("/opt/madar/local-supabase")
SMTP = Path("/etc/madar/secrets/smtp-test.env")
CALLBACKS = {
    "SITE_URL": "https://madarportal.com",
    "API_EXTERNAL_URL": "https://api.madarportal.com",
    "ADDITIONAL_REDIRECT_URLS": "https://madarportal.com/verify-email,https://madarportal.com/reset-password",
}
SMTP_KEYS = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "SMTP_ADMIN_EMAIL", "SMTP_SENDER_NAME")


def configuration_changes(values):
    if (not all(isinstance(values.get(key), str) and values[key] for key in SMTP_KEYS)
            or values["SMTP_HOST"] != "smtp.gmail.com" or values["SMTP_PORT"] != "587"
            or values["SMTP_ADMIN_EMAIL"].casefold() != values["SMTP_USER"].casefold()
            or any(any(char in values[key] for char in ("\n", "\r", "$")) for key in SMTP_KEYS)):
        raise RuntimeError("local_auth_gmail_configuration_invalid")
    return {**CALLBACKS, **{key: values[key] for key in SMTP_KEYS}}


def validate_preparation_evidence(contract, report):
    from deployment.lib.provider_local_transition import validate_evidence, required_gates
    # Only this bounded preparation step admits SMTP PENDING. It cannot issue
    # the normal authorization receipt or call any normal runtime operation.
    gates = report.get("gates", {})
    required = required_gates(report)
    if set(gates) != required or gates.get("auth_smtp") != "PENDING" or any(
            gates[key] != "PASS" for key in required - {"auth_smtp"}):
        raise RuntimeError("local_auth_preparation_gate_incomplete")
    from dataclasses import replace
    ready = {**report, "gates": {**gates, "auth_smtp": "PASS"}}
    # First prove the original contract binds the original PENDING evidence.
    if digest(report) != contract.evidence_digest:
        raise RuntimeError("local_auth_preparation_evidence_changed")
    validate_evidence(replace(contract, evidence_digest=digest(ready)), ready)


def smtp_preflight(values):
    # No debug logging, recipients, DATA or email generation. Certificate and
    # hostname validation remain mandatory; Gmail must offer STARTTLS.
    try:
        with smtplib.SMTP(values["SMTP_HOST"], int(values["SMTP_PORT"]), timeout=15) as smtp:
            smtp.ehlo()
            if not smtp.has_extn("starttls"):
                raise RuntimeError("local_auth_starttls_required")
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
            smtp.login(values["SMTP_USER"], values["SMTP_PASS"])
            code, _ = smtp.mail(values["SMTP_ADMIN_EMAIL"])
            if code != 250:
                raise RuntimeError("local_auth_sender_rejected")
            smtp.rset()
    except (OSError, smtplib.SMTPException):
        raise RuntimeError("local_auth_smtp_preflight_failed") from None


def _restart_auth(ops, compose, image):
    ops.command(compose + ["up", "-d", "--no-deps", "--pull", "never", "auth"])
    for attempt in range(60):
        current = ops.inspect("supabase-auth")
        if current["State"].get("Health", {}).get("Status") == "healthy":
            if current["Image"] != image:
                raise RuntimeError("local_auth_native_image_changed")
            return current
        if attempt == 59:
            raise RuntimeError("local_auth_configuration_unhealthy")
        time.sleep(1)


def configure_auth(ops, contract):
    if os.geteuid() != 0:
        raise RuntimeError("local_auth_root_entry_required")
    ops.recovery.authorize(ops.recovery.contract)
    validate_preparation_evidence(contract, ops.evidence())
    ops.verify_immutable_inputs(contract)
    if ops.transaction_path.exists() or ops.transaction_path.is_symlink():
        raise RuntimeError("local_auth_configuration_after_transition_forbidden")
    values = {}
    load_environment_file(protected(SMTP, private=True), environ=values)
    changes = configuration_changes(values)
    with exclusive_lock(ops.state / "deploy.lock"):
        if ops.fingerprints() != contract.production_fingerprints:
            raise RuntimeError("local_auth_production_changed")
        ops.require_recovery_active(contract.recovery_context)
        ops.require_all_workers_off()
        ops.verify_local_fallback()
        smtp_preflight(values)
        from deployment.lib.provider_local_proxy_configuration import ensure_callback_safe_proxy
        ensure_callback_safe_proxy(ops, contract)
        path = readonly_configuration(NATIVE / ".env")
        native_owner = path.stat()
        before = {}
        load_environment_file(path, environ=before)
        auth = ops.inspect("supabase-auth")
        if not auth["State"]["Running"] or auth["State"].get("Health", {}).get("Status") != "healthy":
            raise RuntimeError("local_auth_native_unhealthy")
        ledger_sql = "SELECT version FROM auth.schema_migrations ORDER BY version;"
        ledger = ops.recovery.target_sql(ledger_sql)
        protected_sql = ("SELECT id,md5(encrypted_password) FROM auth.users ORDER BY id; "
            "SELECT id,md5(secret) FROM auth.mfa_factors ORDER BY id;")
        persistent = ops.recovery.target_sql(protected_sql)
        # Native JWT, encryption, DB keys and current sessions are untouched.
        directory = ops.root / "auth-configuration" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        directory.mkdir(parents=True, mode=0o700)
        archive = directory / "native-before.env"
        with archive.open("xb") as handle:
            handle.write(path.read_bytes()); handle.flush(); os.fsync(handle.fileno())
        os.chmod(archive, 0o600)
        temporary = path.with_name(".governed-auth-configuration.env")
        with temporary.open("x") as handle:
            os.chmod(temporary, 0o600)
            # Preserve every non-mail/callback line byte-for-byte, including
            # existing dotenv quoting of JWT/encryption/database credentials.
            # Rewriting all native values could change Compose interpolation.
            seen = set()
            for line in path.read_text().splitlines(keepends=True):
                match = re.match(r"^([A-Za-z_][A-Za-z_0-9]*)=", line)
                key = match.group(1) if match else None
                if key in changes:
                    handle.write(key + "=" + json.dumps(changes[key]) + "\n")
                    seen.add(key)
                else:
                    handle.write(line)
            if not path.read_bytes().endswith(b"\n"):
                handle.write("\n")
            for key in changes.keys() - seen:
                handle.write(key + "=" + json.dumps(changes[key]) + "\n")
            handle.flush(); os.fsync(handle.fileno())
        os.chown(temporary, native_owner.st_uid, native_owner.st_gid)
        os.replace(temporary, path)
        configured_bytes = path.read_bytes()
        compose = ["docker", "compose", "--project-name", "madar-local-supabase", "--project-directory", str(NATIVE),
            "-f", str(readonly_configuration(NATIVE / "docker-compose.yml", private=False)),
            "-f", str(readonly_configuration(NATIVE / "docker-compose.madar-local.yml", private=False))]
        # Recreate only native Auth, with its unchanged pinned image. No app
        # deployment, worker handoff or automatic application migration occurs.
        try:
            current = _restart_auth(ops, compose, auth["Image"])
            mapped = dict(item.split("=", 1) for item in current["Config"]["Env"])
            expected = {"GOTRUE_SITE_URL": changes["SITE_URL"], "API_EXTERNAL_URL": changes["API_EXTERNAL_URL"],
                "GOTRUE_URI_ALLOW_LIST": changes["ADDITIONAL_REDIRECT_URLS"],
                **{"GOTRUE_"+key: changes[key] for key in SMTP_KEYS}}
            if any(mapped.get(key) != value for key, value in expected.items()):
                raise RuntimeError("local_auth_native_mapping_invalid")
            if ops.recovery.target_sql(ledger_sql) != ledger or ops.recovery.target_sql(protected_sql) != persistent:
                raise RuntimeError("local_auth_ledger_or_persistent_auth_changed")
            ops.require_all_workers_off()
            if ops.fingerprints() != contract.production_fingerprints:
                raise RuntimeError("local_auth_unexpected_production_change")
        except Exception:
            # Governed configuration-only repair, never a database/session
            # rewind. Do not overwrite any unexpected concurrent native edit.
            if path.read_bytes() != configured_bytes:
                raise RuntimeError("local_auth_concurrent_native_configuration_change") from None
            with temporary.open("xb") as handle:
                os.chmod(temporary, 0o600)
                handle.write(archive.read_bytes()); handle.flush(); os.fsync(handle.fileno())
            os.chown(temporary, native_owner.st_uid, native_owner.st_gid)
            os.replace(temporary, path)
            _restart_auth(ops, compose, auth["Image"])
            atomic_json(directory / "configuration-rollback.json", {
                "configuration_restored": True, "database_restored": False, "workers_started": False})
            raise
        atomic_json(directory / "receipt.json", {"schema": 115, "source_sha": contract.sha,
            "preparation_contract_digest": digest(contract.__dict__), "native_image": current["Image"],
            "auth_smtp": "PASS", "starttls": "PASS", "authentication": "PASS", "sender": "PASS",
            "public_mediated_callbacks": "PASS", "application_migrations_executed": False,
            "stable_proxy_callback_redaction": "PASS",
            "auth_ledger_unchanged": True, "password_and_mfa_fingerprints_unchanged": True,
            "database_restore": False, "email_generated": False, "workers_started": False})
