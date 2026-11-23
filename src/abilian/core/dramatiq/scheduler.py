# Copyright (c) 2012-2024, Abilian SAS

"""The periodic tasks: actors queued on a cron schedule by `flask scheduler`."""

from __future__ import annotations

from collections import namedtuple
from typing import TYPE_CHECKING

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Callable

Job = namedtuple("Job", ["actor", "key"])

DEFAULT_SCHEDULE = {
    "SCHEDULE_SEND_DAILY_SOCIAL_DIGEST": "0 10 * * *",
    "PERIODIC_CLEAN_UPLOAD_DIRECTORY": "0 * * * *",
    # No SCHEDULE_CHECK_MAILDIR: the forum sets it on a site that uses a Maildir.
}

_actor_registry = set()


def crontab(crontab: str) -> Callable:
    """Schedule the decorated actor with the cron line in setting `crontab`.

    The default schedules are in `DEFAULT_SCHEDULE`; an empty line, or none,
    leaves the actor unscheduled.
    """

    def decorator(func: Callable) -> Callable:
        # logger.debug("Registering cron job: {func}", func=str(func))
        job = Job(actor=func, key=crontab)
        _actor_registry.add(job)
        return func

    return decorator


def crontab_from_config(config: dict, job: Job) -> str:
    """The cron line of `job` in `config`, else its default; "" for none."""
    key = job.key.upper()
    if key in config:
        # schedule value can be ""
        schedule = config[key].strip()
    else:
        schedule = DEFAULT_SCHEDULE.get(key, "")
    return schedule


def run_scheduler(config: dict) -> int:
    """Queue each scheduled actor on its schedule, until interrupted."""
    scheduler = BlockingScheduler()
    scheduler.remove_all_jobs()

    for job in _actor_registry:
        crontab_content = crontab_from_config(config, job)
        if not crontab_content:
            # A job without a schedule is one the site does not use.
            logger.info(
                "No schedule, cron job not registered: {actor}",
                actor=str(job.actor),
            )
            continue
        # logger.debug(
        #     "Registering cron job: {actor} {crontab}",
        #     actor=str(job.actor),
        #     crontab=crontab_content,
        # )

        scheduler.add_job(
            job.actor.send,
            CronTrigger.from_crontab(crontab_content),
        )

    try:
        scheduler.start()
    except KeyboardInterrupt:
        scheduler.shutdown()

    return 0
