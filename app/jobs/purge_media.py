"""Retention purge job.

Deletes expired media blobs and stamps their tombstones. Run on a schedule
(cron / k8s CronJob / the worker added in Phase 3):

    python -m app.jobs.purge_media
"""
from __future__ import annotations

from app.db import session_scope
from app.logging_config import configure_logging, get_logger
from app.services.retention import purge_expired

log = get_logger("retention_job")


def main() -> int:
    configure_logging()
    with session_scope() as db:
        purged = purge_expired(db)
    log.info("retention_purge_complete", purged=purged)
    return purged


if __name__ == "__main__":
    main()
