"""Retry handler with exponential backoff.

Per SCHED-03: Retry 3 times with delays 5min, 15min, 60min.
"""

import asyncio
import logging
from dataclasses import dataclass, field

from galaxy_db_sync.shared_kernel.utils.config_loader import get_section

logger = logging.getLogger(__name__)


@dataclass
class RetryPolicy:
    """Retry configuration per SCHED-03."""

    max_retries: int = 3
    retry_delays: list[int] = field(default_factory=lambda: [5 * 60, 15 * 60, 60 * 60])  # 5min, 15min, 60min in seconds

    @classmethod
    def from_config(cls) -> "RetryPolicy":
        """Load retry policy from config."""
        config = get_section("scheduler")
        max_retries = config.get("max_retries", 3)
        delays_minutes = config.get("retry_delays_minutes", [5, 15, 60])
        retry_delays = [d * 60 for d in delays_minutes]
        return cls(max_retries=max_retries, retry_delays=retry_delays)


async def sync_with_retry(
    sync_func: callable,
    sync_name: str,
    *args,
    **kwargs
) -> bool:
    """Execute sync with retry policy per SCHED-03.

    Args:
        sync_func: Async function to execute
        sync_name: Human-readable name for logging
        *args: Arguments to pass to sync_func
        **kwargs: Keyword arguments to pass to sync_func

    Returns:
        True if sync succeeded, False if all retries exhausted
    """
    policy = RetryPolicy.from_config()

    for attempt, delay in enumerate(policy.retry_delays, start=1):
        try:
            await sync_func(*args, **kwargs)
            logger.info(f"{sync_name} sync succeeded on attempt {attempt}")
            return True
        except Exception as e:
            logger.error(f"{sync_name} sync failed (attempt {attempt}): {e}")
            if attempt < policy.max_retries:
                logger.info(f"Retrying in {delay // 60} minutes...")
                await asyncio.sleep(delay)

    logger.error(f"{sync_name} sync failed after {policy.max_retries} attempts")
    return False