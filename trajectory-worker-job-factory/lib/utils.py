import signal

from lib.log import logger


class SigtermManager:
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
        logger.info("received sigterm")
        self.should_exit = True


sigterm_manager = SigtermManager()
