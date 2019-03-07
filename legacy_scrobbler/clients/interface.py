import abc

from legacy_scrobbler.listen import Listen, Listens


class ScrobbleClientInterface(abc.ABC):
    @abc.abstractmethod
    def tick(self):
        pass

    @abc.abstractmethod
    def send_nowplaying(self, listens: Listen):
        pass

    @abc.abstractmethod
    def add_listens(self, listens: Listens):
        pass
