"""Bounded, retryable cleanup of unused assessment recordings; dry-run by default."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from services.elearning_recording_service import cleanup

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--limit',type=int,default=100,choices=range(1,501),metavar='1..500')
    args=parser.parse_args()
    print(json.dumps(cleanup(limit=args.limit,apply=args.apply)))
