# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import dramatiq_abort.backends
import redis
from dramatiq.rate_limits import BucketRateLimiter
from dramatiq.rate_limits.backends import (
    RedisBackend as RateLimitRedisBackend,
    StubBackend as RateLimitStubBackend,
)
from dramatiq_abort import Abortable
from loguru import logger

from .cli import scheduler
from .singleton import dramatiq

DEFAULT_DRAMATIQ_ABORT_REDIS_URL = "redis://localhost:6379/0"
DEFAULT_DRAMATIQ_RATE_LIMIT_REDIS_URL = "redis://localhost:6379/0"
RATE_LIMITER = []


# with DISTRIBUTED_MUTEX.acquire():
#         time.sleep(1)
def init_dramatiq_engine(app) -> None:
    if dramatiq.app is not None:
        # ensure only one initialization, especially during tests
        return

    logger.debug("Setting up Dramatiq")
    logger.debug(f"SERVER_NAME: '{app.config.get('SERVER_NAME')}'")
    # for k in (
    #     "DRAMATIQ_RATE_LIMIT_REDIS_URL",
    #     "DRAMATIQ_BROKER_URL",
    #     "DEFAULT_DRAMATIQ_RATE_LIMIT_REDIS_URL",
    # ):
    #     logger.debug(f"{k}: '{app.config.get(k)}'")

    dramatiq.init_app(app)

    _setup_rate_limiter(app)
    _add_dramatiq_abortable(app)
    _register_scheduler(app)

    # Only for debug
    # _print_dramatiq_config()


def _setup_rate_limiter(app) -> None:
    # logger.debug("Add dramatiq rate limiter")
    if app.testing:
        backend = RateLimitStubBackend()
    else:
        backend = RateLimitRedisBackend(client=_rate_limiter_redis_client(app))
    # rate limit is 6/min
    limiter = BucketRateLimiter(backend, "mail-limit", limit=6, bucket=60_000)
    RATE_LIMITER.append(limiter)


def _rate_limiter_redis_client(app) -> redis.Redis:
    redis_url = app.config.get("DRAMATIQ_RATE_LIMIT_REDIS_URL")
    if not redis_url:
        redis_url = app.config.get("DRAMATIQ_BROKER_URL")
    if not redis_url:
        redis_url = DEFAULT_DRAMATIQ_RATE_LIMIT_REDIS_URL
    logger.debug(f"Dramatiq Redis URL: '{redis_url}'")
    return redis.Redis.from_url(redis_url)


def _register_scheduler(app) -> None:
    # logger.debug("Register scheduler")
    app.cli.add_command(scheduler)


def _abortable_redis_client(app) -> redis.Redis:
    redis_url = app.config.get("DRAMATIQ_ABORT_REDIS_URL")
    if not redis_url:
        redis_url = app.config.get("DRAMATIQ_BROKER_URL")
    if not redis_url:
        redis_url = DEFAULT_DRAMATIQ_ABORT_REDIS_URL
    return redis.Redis.from_url(redis_url)


def _add_dramatiq_abortable(app) -> None:
    """Configure abort feature of dramatiq tasks.

    The dramatiq-abort package provides a middleware that can be used to
    abort running actors by message id. Here s how you might set it up:

    @dramatiq.actor
    def a_long_running_task():
        ...

    message = a_long_running_task.send()
    abort(message.message_id)

    abort(message_id, mode=AbortMode.CANCEL)
    abort(message.message_id, mode=AbortMode.ABORT, abort_timeout=2000)
    """
    # logger.debug("Add dramatiq abortable")
    if app.testing:
        backend = dramatiq_abort.backends.StubBackend()
    else:
        backend = dramatiq_abort.backends.RedisBackend(
            client=_abortable_redis_client(app)
        )
    abortable = Abortable(backend=backend)
    dramatiq.broker.add_middleware(abortable)


def _print_dramatiq_config() -> None:
    """Show tasks broker configuration."""
    broker = dramatiq.broker
    messages = []
    messages.append("Dramatiq broker in app:")
    messages.append(f"{broker=}")
    messages.append("broker middlewares:")
    middlewares = ", ".join([str(mw.__class__.__name__) for mw in broker.middleware])
    messages.append(middlewares)
    messages.append("broker.get_declared_queues():")
    messages.append(str(broker.get_declared_queues()))
    messages.append("broker.get_declared_actors():")
    messages.append(str(broker.get_declared_actors()))
    for msg in messages:
        logger.debug(msg)
