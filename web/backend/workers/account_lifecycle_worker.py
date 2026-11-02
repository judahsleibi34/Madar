"""Opt-in protocol3 worker; never starts as a side effect of importing a service."""
import os
import socket
import time
from uuid import uuid4


def main():
    if os.getenv("ACCOUNT_LIFECYCLE_WORKER_ENABLED","false").lower()!="true":return 0
    from database import service_supabase
    from services.account_erasure_service import run_batch
    owner=f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"
    once=os.getenv("ACCOUNT_LIFECYCLE_WORKER_ONCE","false").lower()=="true"
    while True:
        run_batch(worker_id=owner,client=service_supabase)
        if once:return 0
        time.sleep(5)


if __name__=="__main__":raise SystemExit(main())
