import abc
from collections import deque

from legacy_scrobbler.listen import Listen, Listens
from legacy_scrobbler.delay import Delay


class ScrobbleClientInterface(abc.ABC):
    @abc.abstractmethod
    def __init__(self):
        self.hard_fails = 0
        self.queue = deque()
        self.np = None
        self.delay = Delay(
            options={
                "base": 60,  # 1 minute base
                "max": 7200,  # 120 minutes max
                "multiplier": 2,
            }
        )

    @abc.abstractmethod
    def tick(self):
        pass

    @abc.abstractmethod
    def send_nowplaying(self, listens: Listen):
        pass

    @abc.abstractmethod
    def add_listens(self, listens: Listens):
        pass
