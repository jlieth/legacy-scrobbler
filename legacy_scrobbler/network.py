import hashlib
import time
from typing import Iterable

from legacy_scrobbler.listen import Listen
from legacy_scrobbler.requests import HandshakeRequest, PostRequest
from legacy_scrobbler.version import __version__


class Network:
    """
    This class represents a scrobble service and offers methods to communicate
    with the service according to the Audioscrobbler 1.2 protocol.

    The methods for communication are:
    - Network.handshake(): Attempt handshake with the remote server to receive
      a session id
    - Network.nowplaying(listen): Send nowplaying information about the given
      listen object to the remote server
    - Network.scrobble(listens): Send scrobble information about all given
      listen objects to the remote server

    Note that this class does not implement any of the error handling mechanism
    suggested in the Audioscrobbler protocol. Whenever anything unexpected
    happens, the server response indicates an error or an exception is raised
    by the requests library, this class will raise an exception of its own.
    It is up to the code using this class to catch these exceptions and
    implement the necessary exception handling logic.
    """

    CLIENT_NAME = "legacy"
    CLIENT_VERSION = __version__

    def __init__(
        self, name: str, username: str, password_hash: str, handshake_url: str
    ):
        """
        Create a Network object.

        :param name: String. Name of the scrobbler network.
        :param username: String. Name of the user on the scrobbler network.
        :param password_hash: String. md5-hashed password of the given user.
            Hash the password before passing it to the constructor. Do not
            give the plaintext password.
        :param handshake_url: String. Url of the handshake endpoint of the
            scrobble service
        """
        self.name = name
        self.username = username
        self.password_hash = password_hash.encode("utf-8")
        self.handshake_url = handshake_url

        self.nowplaying_url = None
        self.scrobble_url = None
        self.session = None

    def handshake(self):
        """
        Sends a handshake request to the remote scrobbler server.
        """
        # create auth token, which is md5(md5(password) + timestamp)
        # password is already hashed so we don't need the inner md5(password)
        timestamp = str(int(time.time())).encode("utf-8")
        auth = hashlib.md5(self.password_hash + timestamp).hexdigest()

        params = {
            "hs": "true",
            "p": "1.2",
            "c": self.CLIENT_NAME,
            "v": self.CLIENT_VERSION,
            "u": self.username,
            "t": timestamp,
            "a": auth,
        }

        # make request
        result = HandshakeRequest(self.handshake_url, params).execute()
        self.session, self.nowplaying_url, self.scrobble_url = result

    def nowplaying(self, listen: Listen):
        """
        Sends a nowplaying request for the given Listen to the scrobbler service.

        :param listen: A Listen object
        """
        data = listen.nowplaying_params()
        data["s"] = self.session
        PostRequest(self.nowplaying_url, data).execute()

    def scrobble(self, listens: Iterable[Listen]):
        """
        Scrobbles the given Listens to the scrobbler service.

        :param listens: Iterable of Listen objects
        """
        data = self._get_scrobble_params(listens)
        data["s"] = self.session
        PostRequest(self.scrobble_url, data).execute()

    @staticmethod
    def _get_scrobble_params(listens: Iterable[Listen]) -> dict:
        """
        Utility function that generates the param dict for a scrobble request
        from the sequence of Listen objects handed to the function.

        :param listens: Iterable of Listen objects
        :return: dict of params used in a scrobble request
        """
        params = {}
        for i, listen in enumerate(listens):
            scrobble_params = listen.scrobble_params(idx=i)
            params.update(scrobble_params)

        return params
