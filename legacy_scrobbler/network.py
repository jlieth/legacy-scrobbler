import hashlib
import time
from typing import Iterable

import requests

from legacy_scrobbler.exceptions import (
    HardFailureError,
    RequestsError,
    ClientBannedException,
    BadAuthException,
    BadTimeException,
    BadSessionError,
    SubmissionWithoutListensError,
)
from legacy_scrobbler.listen import Listen
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

        :raises legacy_scrobbler.exceptions.HardFailureError: If the status
            code of the response isn't 200
        :raises legacy_scrobbler.exceptions.RequestsError: If executing the
            request with the requests library raises any in that library
            defined exceptions

        This function calls Network._process_handshake_response() to process
        the response, so these additional exceptions raised by that function
        are possible:

        :raises legacy_scrobbler.exceptions.ClientBannedException: If the
            response from the server is "BANNED"
        :raises legacy_scrobbler.exceptions.BadAuthException: If the response
            from the server is "BADAUTH"
        :raises legacy_scrobbler.exceptions.BadTimeException: If the response
            from the server is "BADTIME"
        :raises legacy_scrobbler.exceptions.HardFailureError: If the response
            from the server is neither "OK" nor any of the possible errors
            defined above
        """
        # create auth token, which is md5(md5(password) + timestamp) per protocol
        # password is already saved as hash so we don't need the inner md5(password)
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

        # make request, catch exceptions if necessary and raise own exceptions
        try:
            r = requests.get(self.handshake_url, params=params, timeout=5)
            r.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise HardFailureError(e)
        except requests.exceptions.RequestException as e:
            msg = f"Exception from underlying requests library: {e}"
            raise RequestsError(msg)

        # process the response (which might raise more exceptions)
        self._process_handshake_response(r)

    def nowplaying(self, listen: Listen):
        """
        Sends a nowplaying request for the given Listen to the scrobbler service.
        This function calls Network._make_post_request() to make the actual
        request. Please see over there for a list of possible exceptions.

        :param listen: A Listen object
        """
        self._make_post_request(request_type="nowplaying", listens=(listen,))

    def scrobble(self, listens: Iterable[Listen]):
        """
        Scrobbles the given Listens to the scrobbler service.
        This function calls Network._make_post_request() to make the actual
        request. Please see over there for a list of possible exceptions.

        :param listens: Iterable of Listen objects
        """
        self._make_post_request(request_type="scrobble", listens=listens)

    def _make_post_request(
        self, request_type: str = "nowplaying", listens: Iterable[Listen] = None
    ):
        """
        Utility function used to make POST requests to the online scrobble
        service. Both scrobble and nowplaying requests are POST requests
        and are basically identical except for the query params and the
        endpoint url. This function is internally called by both
        Network.scrobble() and Network.nowplaying() to make the actual request.

        :param request_type: String. Either "scrobble" or "nowplaying".
        :param listens: Iterable of Listen objects
        :raises legacy_scrobbler.exceptions.BadSessionError: If no session
            is saved in the Network object when this function is called
            OR if the server response after the request is "BADSESSION"
            (through Network._process_post_response())
        :raises legacy_scrobbler.exceptions.SubmissionWithoutListensError: If
            the Sequence of Listen objects is empty.
        :raises legacy_scrobbler.exceptions.HardFailureError: If the status
            code from the server after the request isn't 200
            OR if the response from the server isn't defined in the
            Audioscrobbler protocol (through Network._process_post_response())
        :raises legacy_scrobbler.exceptions.RequestsError: If executing the
            request with the requests library raises any in that library
            defined exceptions
        """
        # raise Exception if no session exists at this point
        if self.session is None:
            raise BadSessionError("No session exists at time of submission attempt")

        # raise exception if list of listens is empty
        if not listens or len(listens) == 0:
            raise SubmissionWithoutListensError()

        # generate params and get url dependent on request_type
        if request_type == "scrobble":
            params = self._get_scrobble_params(listens)
            url = self.scrobble_url
        else:
            params = listens[0].nowplaying_params()
            url = self.nowplaying_url

        # add session_id to params
        params["s"] = self.session

        # make request and catch exceptions if necessary
        try:
            r = requests.post(url, data=params)
            r.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise HardFailureError(e)
        except requests.exceptions.RequestException as e:
            msg = f"Exception from underlying requests library: {e}"
            raise RequestsError(msg)

        self._process_post_response(r)

    def _process_handshake_response(self, r):
        """
        Processes the response from a handshake request. Called by
        Network.handshake() after the request has been made. The response
        after a valid handshake contains information such as the session_id
        that is saved in the Network object after response validation.

        :param r: Response object from a requests Request
        :raises legacy_scrobbler.exceptions.ClientBannedException: If the
            response from the server is "BANNED"
        :raises legacy_scrobbler.exceptions.BadAuthException: If the response
            from the server is "BADAUTH"
        :raises legacy_scrobbler.exceptions.BadTimeException: If the response
            from the server is "BADTIME"
        :raises legacy_scrobbler.exceptions.HardFailureError: If the response
            from the server is neither "OK" nor any of the possible errors
            defined above
        """
        result = r.text.split("\n")
        if len(result) >= 4 and result[0] == "OK":
            self.session = result[1]
            self.nowplaying_url = result[2]
            self.scrobble_url = result[3]
            return
        elif result[0] == "BANNED":
            raise ClientBannedException()
        elif result[0] == "BADAUTH":
            raise BadAuthException()
        elif result[0] == "BADTIME":
            raise BadTimeException()
        else:
            raise HardFailureError(r.text)

    def _process_post_response(self, r):
        """
        Processes the response from one of the post requests (scrobble and
        nowplaying). Called by Network._make_post_request() after the
        request has been made.

        :param r: Response object from a requests Request
        :raises legacy_scrobbler.exceptions.BadSessionError: If the response
            from the server is "BADSESSION"
        :raises legacy_scrobbler.exceptions.HardFailureError: If the response
            from the server is neither "OK" nor "BADSESSION" and thus
            not in the Audioscrobbler protocol.
        """
        if r.text.startswith("OK"):
            return
        elif r.text.startswith("BADSESSION"):
            raise BadSessionError("Remote server says the session is invalid")
        else:
            raise HardFailureError(r.text)

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
