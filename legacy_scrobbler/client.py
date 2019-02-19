from collections import deque
import datetime
import logging

from legacy_scrobbler.exceptions import HandshakeError, HardFailureError
from legacy_scrobbler.listen import Listen
from legacy_scrobbler.network import Network


logger = logging.getLogger("legacy_scrobbler")


class ScrobblerClient(Network):
    def __init__(
        self, name: str, username: str, password_hash: str, handshake_url: str
    ):
        super().__init__(name, username, password_hash, handshake_url)

        self.state = "no_session"
        self.delay = 0
        self.hard_fails = 0
        self.last_handshake = None
        self.queue = deque()

    def tick(self):
        if self.state == "no_session" and self._allowed_to_handshake:
            logger.info("Executing handshake attempt")
            self._execute_handshake()

    def enqueue_listens(self, *listens: Listen):
        self.queue.extend(listens)
        self._sort_queue()

    def _execute_handshake(self):
        try:
            self.state = "handshaking"
            self.handshake()
        except HandshakeError as e:
            # that's a fatal error and can't be handled
            logger.error(f"Fatal error during handshake phase: {e}")
            raise
        except HardFailureError as e:
            self.hard_fails += 1
            self._increase_delay()
            self.state = "no_session"
            logger.warning(f"Hard failure during handshake attempt: {e}.")
            logger.info(f"Number of hard failures is now {self.hard_fails}.")
            logger.info(f"Delay is now {self.delay} seconds.")
        else:
            self.hard_fails = 0
            self.delay = 0
            self.state = "idle"
            logger.info("Handshake successful.")
        finally:
            self.last_handshake = datetime.datetime.now(datetime.timezone.utc)

    @property
    def _allowed_to_handshake(self) -> bool:
        time_until = self._time_to_next_handshake
        if time_until.seconds > 0:
            logger.info(f"Next handshake attempt allowed in {time_until}")
            return False
        else:
            return True

    @property
    def _time_to_next_handshake(self) -> datetime.timedelta:
        """
        Calculate the time that has to elapse until the next handshake may
        be attempted.

        Will return a timedelta of zero if self.delay is zero or
        self.last_handshake is None.
        """
        # if no delay is set, timedelta is zero
        if self.delay == 0:
            return datetime.timedelta(seconds=0)

        # if no last_handshake is set, timedelta is zero
        if self.last_handshake is None:
            return datetime.timedelta(seconds=0)

        # if the time of the last handshake plus the delay is earlier
        # than now, timedelta is zero (since no time needs to pass until
        # the next handshake attempt may be made)
        delay_delta = datetime.timedelta(seconds=self.delay)
        next_handshake = self.last_handshake + delay_delta
        now = datetime.datetime.now(self.last_handshake.tzinfo)

        if next_handshake <= now:
            return datetime.timedelta(seconds=0)
        else:
            return next_handshake - now

    def _sort_queue(self):
        self.queue = deque(sorted(self.queue, key=lambda listen: listen.date))

    def _increase_delay(self):
        self.delay = (self.delay * 2) or 60

        if self.delay > 120 * 60:
            self.delay = 120 * 60
