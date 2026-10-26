#!/usr/bin/env python3
"""Generate an exact-source CI preparation plan; never an operational receipt."""
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deployment.lib.migration_inventory import discover,canonical
from deployment.lib.migration_plan import generate


def main():
    root=Path(__file__).resolve().parents[2]
    source=os.environ['CI_SOURCE_SHA']; baseline=os.environ['CI_HISTORY_BASE_SHA']
    # CI supplies the event's base independently from migration-author metadata.
    # Production still authenticates protected integration and applied history.
    before=discover(root,source_sha=baseline,history_base_sha=baseline)
    inventory=discover(root,source_sha=source,history_base_sha=baseline)
    plan=generate(root,inventory,origin=before.target)
    sys.stdout.buffer.write(plan.encoded)
    return 0


if __name__=='__main__': raise SystemExit(main())
