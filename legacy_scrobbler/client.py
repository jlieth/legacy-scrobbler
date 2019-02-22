from collections import deque
import datetime
import itertools
import logging
from typing import Callable, Iterable, Union

from legacy_scrobbler.exceptions import (
    HandshakeError,
    HardFailureError,
    RequestsError,
    BadSessionError,
    SubmissionWithoutListensError,
)
from legacy_scrobbler.listen import Listen
from legacy_scrobbler.network import Network


logger = logging.getLogger("legacy_scrobbler")

# types
Listens = Iterable[Listen]
Listen_or_list_of_Listens = Union[Listens, Listen]


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
        self.np = None

    def tick(self):
        """
        Tick function. Should be called from a main loop. Checks internal
        state on each call and performs appropriate actions if the situation
        calls for it. For example, if the internal state is "no_session", the
        tick function will execute a handshake attempt. A handshake attempt
        can be either successful or failed so on the next tick, the internal
        state might still be "no_session" (on failure) or "idle" (on success).
        """

        def on_successful_handshake():
            """
            Callback after a successful handshake request. Resets hard failure
            counter and delay, and sets self.state to idle.
            """
            self.hard_fails = 0
            self.delay = 0
            self.state = "idle"
            logger.info(f"Handshake successful. Received session id {self.session}")

        def after_handshake_attempt():
            """
            Callback after handshake attempt (regardless of success). Sets
            self.last_handshake to current datetime
            """
            self.last_handshake = datetime.datetime.now(datetime.timezone.utc)

        def on_successful_nowplaying():
            """
            Callback after a successful nowplaying request. Sets self.np back
            to None.
            """
            self.np = None
            logger.info("Nowplaying successful")

        def on_successful_scrobble():
            """
            Callback after a successful scrobble request. Each scrobble request
            can submit 50 scrobbles at once. After a successful scrobble, we
            can assume that the first 50 scrobbles in queue have been submitted
            and can be removed from the queue.
            """
            self.queue = deque(itertools.islice(self.queue, 50, None))
            logger.info(
                f"Scrobbling successful. Length of remaining queue "
                f"is now {len(self.queue)}"
            )

        # if no session exists and handshake attempt is allowed right now,
        # execute handshake
        if self.state == "no_session" and self._allowed_to_handshake:
            logger.info("Executing handshake attempt")
            self._execute_request(
                method=self.handshake,
                else_cb=on_successful_handshake,
                finally_cb=after_handshake_attempt,
            )

        # if state is idle, check if a nowplaying request should be made
        elif self.state == "idle" and self.np is not None:
            logger.info("Executing nowplaying attempt")
            self._execute_request(
                method=self.nowplaying, else_cb=on_successful_nowplaying, arg=self.np
            )

        # if state is idle, check if any scrobbles are queued
        elif self.state == "idle" and len(self.queue) > 0:
            logger.info("Executing scrobbling attempt")
            scrobble_slice = deque(itertools.islice(self.queue, 0, 50))
            self._execute_request(
                method=self.scrobble, else_cb=on_successful_scrobble, arg=scrobble_slice
            )

    def set_nowplaying(self, listen: Listen):
        """
        Sets the given Listen as the nowplaying track. Nowplaying request
        will be send on the next tick (when self.state is "idle").

        :param listen: Listen object
        """
        self.np = listen

    def enqueue_listens(self, listens: Listens):
        """
        Adds the given Listen objects to the queue so they can be scrobbled
        on the next tick (when scrobbling is possible).

        :param listens: Iterable of Listen objects that should be scrobbled
        """
        self.queue.extend(listens)
        self._sort_queue()

    def _execute_request(
        self,
        method: Callable,
        else_cb: Callable = None,
        finally_cb: Callable = None,
        arg: Listen_or_list_of_Listens = None,
    ):
        """
        Executes the given request method with the given arg and adds exception
        handling. Request method has to be either self.handshake,
        self.nowplaying or self.scrobble

        Catches all exceptions that can be raised by any of the methods.
        List of possible exceptions:
        - raised by all methods: HardFailureError and RequestsError
        - only raised by handshake: HandshakeError (with three Exceptions
          inheriting from it but catching this exception is all we need to do)
        - only raised by nowplaying and scrobble: BadSessionError and
          SubmissionWithoutListensError

        :param method: Callable. One of self.handshake, self.nowplaying and
            self.scrobble
        :param else_cb: Callable. Function that will be called in the else
            block of the try/except/else/finally construct (i.e. actions to be
            taken on successful completion of the request). No arguments.
        :param finally_cb: Callable. Function that will be called in the finally
            block of the try/except/else/finally construct (i.e. actions to be
            taken regardless of success of the request, such as cleanup tasks).
            No arguments.
        :param arg: One Listen object if method is nowplaying, list of Listen
            objects if method is scrobble, None if method is handshake
        """
        assert method in [self.handshake, self.nowplaying, self.scrobble]
        req_type = method.__name__

        try:
            method(arg) if arg else method()
        except HardFailureError as e:
            # raised by any of the three methods. non-fatal, just call
            # _in_case_of_failure to increment failure counter and delay
            logger.warning(f"Hard failure during {req_type} attempt: {e}.")
            self._in_case_of_failure()
        except RequestsError as e:
            # raised by any of the three methods. non-fatal (for now), just
            # call _in_case_of_failure to increment failure counter and delay
            logger.error(f"Requests Exception during {req_type} attempt: {e}")
            self._in_case_of_failure()
        except BadSessionError as e:
            # session id is invalid, client should re-handshake on next tick
            logger.warning(
                f"{e}. self.session is {self.session}. Falling back to handshake phase"
            )
            self.state = "no_session"
            self.session = None
        except HandshakeError as e:
            # raised during handshake. fatal error, re-raise
            logger.error(f"Fatal error during {req_type} attempt: {e}")
            raise
        except SubmissionWithoutListensError:
            # Your friendly neighbourhood programmer has messed up somewhere.
            # Please file a bug report or something.
            msg = (
                "You tried to make a submission without any Listen objects. "
                "There's an error somewhere in the calling code that made "
                "the request."
            )
            logger.error(msg)
            raise
        else:
            if else_cb:
                else_cb()
        finally:
            if finally_cb:
                finally_cb()

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
