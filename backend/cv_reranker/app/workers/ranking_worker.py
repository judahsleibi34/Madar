from __future__ import annotations

import logging
import os
import socket
import time
import uuid
from datetime import UTC, datetime
from typing import cast

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.models import WorkerInstance
from app.db.session import get_sync_session
from app.services.jobs.worker import JobProcessor, claim_next_job, recover_stale_jobs
from app.services.ranking.reranker import Reranker, SentenceTransformerReranker

logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    settings.ensure_storage()
    os.environ.setdefault("OMP_NUM_THREADS", str(settings.omp_num_threads))
    os.environ.setdefault("MKL_NUM_THREADS", str(settings.mkl_num_threads))
    worker_id = uuid.uuid4()
    reranker = SentenceTransformerReranker(settings)
    processor = JobProcessor(settings, cast(Reranker, reranker), worker_id)
    with get_sync_session() as db:
        db.add(
            WorkerInstance(
                id=worker_id,
                worker_name=f"{socket.gethostname()}:{os.getpid()}",
                model_id=reranker.model_id,
                backend=reranker.backend,
                model_loaded=True,
            )
        )
        db.commit()
    while True:
        try:
            with get_sync_session() as db:
                recover_stale_jobs(db, settings)
                instance = db.get(WorkerInstance, worker_id)
                if instance:
                    instance.heartbeat_at = datetime.now(UTC)
                    db.commit()
                job_id = claim_next_job(db, worker_id)
            if job_id is None:
                time.sleep(settings.worker_poll_interval_seconds)
                continue
            with get_sync_session() as db:
                processor.process(db, job_id)
        except KeyboardInterrupt:
            return
        except Exception:
            logger.exception("worker_iteration_failed", extra={"event": "worker_iteration_failed"})
            time.sleep(settings.worker_poll_interval_seconds)


if __name__ == "__main__":
    main()
