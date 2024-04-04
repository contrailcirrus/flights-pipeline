import signal
from datetime import datetime, timedelta
from typing import Iterator

from lib.log import logger


class SigtermHandler:
    def __init__(self):
        """Ensure workload gracefully exits on SIGTERM signal.

        Examples
        --------
        sigterm_handler = SigtermHandler()
        while not sigterm_handler.should_exit:
            print('Still iterating!')
            time.sleep(1)
        """
        self.should_exit = False
        signal.signal(signal.SIGTERM, self._handler)

    def _handler(self, *args, **kwargs):
        logger.info("Received SIGTERM.")
        self.should_exit = True


def time_windows(
    start_at: datetime, end_at: datetime, step: timedelta
) -> Iterator[tuple[datetime, datetime]]:
    """Constructs ordered time windows between start_at and end_at of size step.

    Parameters
    ----------
    start_at
        time at which first window should begin, inclusive.
    end_at
        time at which last window should end, inclusive, if end_at - start_at is evenly
        divisible by step. If end_at - start_at is not evenly divisible by step, the
        last window returned will be:
            [start_at + (n) * step, start_at + (n + 1) * step)
        where (start_at + (n + 1) * step) < end_at. In other words, all windows will be
        of length step and no partial windows will be returned.

    Yields
    ------
    tuple[window_start_at, window_end_at]
        indicates bounds of each window where start_at <= window_start_at < end_at and
        start_at < window_end_at <= end_at
    """
    next_start_at = start_at
    next_end_at = next_start_at + step
    while next_end_at <= end_at:
        yield (next_start_at, next_end_at)
        next_start_at = next_end_at
        next_end_at = next_start_at + step
