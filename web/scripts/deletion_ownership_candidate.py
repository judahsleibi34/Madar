"""Checksum-pinned unselected deletion ownership successor; no SQL execution."""
import importlib.util
from pathlib import Path


def validated_entries(root):
    path=Path(__file__).resolve().parents[1]/'deployment/lib/schema150_release.py'
    spec=importlib.util.spec_from_file_location('deletion150_source_contract',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    try:
        rows=module.source_manifest(root)['migrations']
    except RuntimeError as error:
        raise ValueError('Deletion ownership candidate contract invalid') from error
    return [row for row in rows if row['number']==150]
