#!/usr/bin/env python3
"""Generate the auditable plan matrix and shared capability identifiers."""
import argparse
import importlib.util
import json
from pathlib import Path

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('commercial_catalog',root/'backend/services/commercial_catalog.py')
catalog=importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)
contract={'version':catalog.CATALOG_VERSION,'capabilities':list(catalog.CAPABILITIES),
          'plans':{plan:{cap:cap in catalog.get_product(plan)['capabilities'] for cap in catalog.CAPABILITIES} for plan in catalog.BASE_PLAN_IDS}}
rendered=json.dumps(contract,indent=2,sort_keys=True)+'\n'
parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
target=root/'frontend/src/commercial/planMatrix.generated.json'
if args.check:
    if not target.is_file() or target.read_text()!=rendered:raise SystemExit('Commercial contract is stale; run web/scripts/generate_commercial_contract.py')
else:
    target.write_text(rendered)
print(f'Commercial contract: {len(contract["plans"])} plans, {len(contract["capabilities"])} capabilities')
