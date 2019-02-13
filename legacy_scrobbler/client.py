from collections import deque
import datetime
import logging

from legacy_scrobbler.exceptions import HandshakeError, HardFailureError


logger = logging.getLogger("legacy_scrobbler")


class ScrobblerClient:
    def __init__(self, network):
        self.network = network

        self.state = "no_session"
        self.delay = 0
        self.hard_fails = 0
        self.last_handshake = None
        self.listens_queue = deque()

    def tick(self):
        if self.state == "no_session" and self._allowed_to_handshake:
            logger.info("Executing handshake attempt")
            self._execute_handshake()

    def _execute_handshake(self):
        try:
            self.state = "handshaking"
            self.network.handshake()
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
        # if no delay is set, client may handshake again
        if self.delay == 0:
            return True

        # if no last_handshake is set, client may handshake despite delay
        if self.last_handshake is None:
            return True

        # if the timedelta between the last handshake and now is greater than
        # the delay, the client may handshake again
        now = datetime.datetime.now(self.last_handshake.tzinfo)
        timedelta_since_last_handshake = now - self.last_handshake
        delay_has_passed = timedelta_since_last_handshake.seconds >= self.delay

        if delay_has_passed:
            return True
        else:
            next_delta = self._time_to_next_handshake
            logger.debug(f"Next handshake attempt allowed in {next_delta}")
            return False

    @property
    def _time_to_next_handshake(self) -> datetime.timedelta:
        delay_delta = datetime.timedelta(seconds=self.delay)
        next_handshake = self.last_handshake + delay_delta
        now = datetime.datetime.now(self.last_handshake.tzinfo)
        return next_handshake - now

    def _increase_delay(self):
        self.delay = (self.delay * 2) or 60

        if self.delay > 120 * 60:
            self.delay = 120 * 60
