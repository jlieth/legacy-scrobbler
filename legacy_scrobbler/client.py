from collections import deque
import datetime
import logging
from typing import Iterable

from legacy_scrobbler.exceptions import HandshakeError, HardFailureError, RequestsError
from legacy_scrobbler.listen import Listen
from legacy_scrobbler.network import Network


logger = logging.getLogger("legacy_scrobbler")


class ScrobblerClient(Network):
    """
    Client-side implementation of the Audioscrobbler protocol 1.2

    Inherits from legacy_scrobbler.network.Network and adds error handling,
    request delays and timing functionality through a tick() function that can
    be called from a main loop.

    Instead of calling the nowplaying() and scrobble() methods directly,
    Listens should be enqueued with the enqueue_listens() method
    TODO: nowplaying

    The handshake() method should never be called on ScrobblerClient objects
    because they manage their internal state automatically.
    """

    def __init__(
        self, name: str, username: str, password_hash: str, handshake_url: str
    ):
        """
        Creates a ScrobblerClient object. Inherits from
        legacy_scrobbler.network.Network. Arguments are the same. Please
        refer to the Network documentation for details about arguments.
        """
        super().__init__(name, username, password_hash, handshake_url)

        self.state = "no_session"
        self.delay = 0
        self.hard_fails = 0
        self.last_handshake = None
        self.queue = deque()

    def tick(self):
        """
        Tick function. Should be called from a main loop. Checks internal
        state on each call and performs appropriate actions if the situation
        calls for it. For example, if the internal state is "no_session", the
        tick function will execute a handshake attempt. A handshake attempt
        can be either successful or failed so on the next tick, the internal
        state might still be "no_session" (on failure) or "idle" (on success).
        """
        if self.state == "no_session" and self._allowed_to_handshake:
            logger.info("Executing handshake attempt")
            self._execute_handshake()

    def enqueue_listens(self, listens: Iterable[Listen]):
        """
        Adds the given Listen objects to the queue so they can be scrobbled
        on the next tick (when scrobbling is possible).

        :param listens: Iterable of Listen objects that should be scrobbled
        """
        self.queue.extend(listens)
        self._sort_queue()

    def _execute_handshake(self):
        """
        Calls self.handshake(), catching any exceptions that might occur
        and setting the internal state depending on the outcome.
        """
        try:
            self.handshake()
        except HandshakeError as e:
            # that's a fatal error and can't be handled
            logger.error(f"Fatal error during handshake phase: {e}")
            raise
        except HardFailureError as e:
            # hard failures are not fatal. self._in_case_of_failure increases
            # failure counter and delay for next handshake attempts
            logger.warning(f"Hard failure during handshake attempt: {e}.")
            self._in_case_of_failure()
        except RequestsError as e:
            # requests exceptions are not fatal (for now).
            # self._in_case_of_failure increases failure counter and delay
            # for next handshake attempts
            logger.error(f"Requests Exception during handshake attempt: {e}")
            self._in_case_of_failure()
        else:
            # reset failure counter and delay on successful handshake and
            # set state to idle
            self.hard_fails = 0
            self.delay = 0
            self.state = "idle"
            logger.info("Handshake successful.")
        finally:
            # set last handshake time to now regardless of success
            self.last_handshake = datetime.datetime.now(datetime.timezone.utc)

    @property
    def _allowed_to_handshake(self) -> bool:
        """
        Determines whether a handshake attempt is permitted right now.

        :return: bool. Whether or not a handshake attempt is permitted now
        """
        time_until = self._time_to_next_handshake
        if time_until.seconds > 0:
            logger.info(f"Next handshake attempt allowed in {time_until}")
            return False
        else:
            return True

    @property
    def _time_to_next_handshake(self) -> datetime.timedelta:
        """
        Calculates the time that has to elapse until the next handshake may
        be attempted.

        Will return a timedelta of zero if self.delay is zero or
        self.last_handshake is None.

        :return: datetime.timedelta: Timedelta until next handshake is allowed
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
        """Sorts self.queue by date of listens objects in queue"""
        self.queue = deque(sorted(self.queue, key=lambda listen: listen.date))

    def _in_case_of_failure(self):
        """
        Executes common tasks in case of a request failure.
        - increases hard failure counter
        - calls self._increase_delay()
        - if number of failures >= 3, the client falls back to handshake phase
        """
        self.hard_fails += 1
        self._increase_delay()
        logger.info(f"Number of hard failures is now {self.hard_fails}.")
        logger.info(f"Delay is now {self.delay} seconds.")

        # fall back to handshake phase if failure count >= 3
        if not self.state == "no_session" and self.hard_fails >= 3:
            self.state = "no_session"
            logger.info("Falling back to handshake phase")

    def _increase_delay(self):
        """
        Increases self.delay according to Audioscrobbler protocol.
        Delay starts at zero, first failure results in delay of 1 minute,
        every consecutive failure doubles the delay up to 120 minutes.
        """
        self.delay = (self.delay * 2) or 60

        if self.delay > 120 * 60:
            self.delay = 120 * 60
