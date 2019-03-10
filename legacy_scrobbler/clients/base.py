import abc
from collections import deque
import itertools
import logging
from typing import Callable, Union

from legacy_scrobbler.listen import Listen, Listens
from legacy_scrobbler.delay import Delay

logger = logging.getLogger("legacy_scrobbler")


class ScrobbleClientBase(abc.ABC):
    @abc.abstractmethod
    def __init__(self):
        self.state = "no_session"
        self.queue = deque()
        self.np = None
        self.hard_fails = 0
        self.delay = Delay(
            options={
                "base": 60,  # 1 minute base
                "max": 7200,  # 120 minutes max
                "multiplier": 2,
            }
        )

    @abc.abstractmethod
    def tick(self):  # pragma: no cover
        pass

    def send_nowplaying(self, listen: Listen):
        """
        Sets the given Listen as the nowplaying track. Nowplaying request
        will be send on the next tick (when self.state is "idle").

        :param listen: Listen object
        """
        self.np = listen

    def add_listens(self, listens: Listens):
        """
        Adds the given Listen objects to the queue so they can be scrobbled
        on the next tick (when scrobbling is possible).

        :param listens: Iterable of Listen objects that should be scrobbled
        """
        self.queue.extend(listens)
        self._sort_queue()

    @abc.abstractmethod
    def handshake(self):  # pragma: no cover
        pass

    @abc.abstractmethod
    def nowplaying(self, listen: Listen):  # pragma: no cover
        pass

    @abc.abstractmethod
    def scrobble(self, listens: Listens):  # pragma: no cover
        pass

    @abc.abstractmethod
    def _execute_request(
        self,
        method: Callable,
        else_cb: Callable = None,
        finally_cb: Callable = None,
        arg: Union[Listens, Listen] = None,
    ):
        """
        Executes the given request method with the given arg and adds exception
        handling. Request method has to be either self.handshake,
        self.nowplaying or self.scrobble

        :param method: Callable. One of self.handshake, self.nowplaying and
            self.scrobble
        :param else_cb: Callable. Function that will be called in the else
            block of the try/except/else/finally construct.
        :param finally_cb: Callable. Function that will be called in the
            finally block of the try/except/else/finally construct.
        :param arg: One Listen object if method is nowplaying, list of Listen
            objects if method is scrobble, None if method is handshake
        """
        pass

    def _sort_queue(self):
        """Sorts self.queue by date of listens objects in queue"""
        self.queue = deque(sorted(self.queue, key=lambda listen: listen.date))

    def on_handshake(self):
        """
        Callback after handshake attempt (regardless of success). Calls
        self.delay.update() to set delay start time to now.
        """
        self.delay.update()

    def on_handshake_success(self):
        """
        Callback after a successful handshake request. Resets hard failure
        counter and delay, and sets self.state to idle.
        """
        self.hard_fails = 0
        self.delay.reset()
        self.state = "idle"
        logger.info(f"Handshake successful")

    def on_nowplaying_success(self):
        """
        Callback after a successful nowplaying request. Sets self.np back
        to None.
        """
        self.np = None
        logger.info("Nowplaying successful")

    def on_scrobble_success(self):
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
