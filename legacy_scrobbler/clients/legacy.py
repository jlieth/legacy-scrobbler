import hashlib
import logging
import time
from typing import Callable, Union

from legacy_scrobbler.clients.base import ScrobbleClientBase
from legacy_scrobbler.listen import Listen, Listens
from legacy_scrobbler.requests import HandshakeRequest, PostRequest
from legacy_scrobbler.version import __version__
from legacy_scrobbler.exceptions import (
    HandshakeError,
    HardFailureError,
    RequestsError,
    BadSessionError,
    SubmissionWithoutListensError,
)

logger = logging.getLogger("legacy_scrobbler")


class LegacyScrobbler(ScrobbleClientBase):
    """Client-side implementation of the Audioscrobbler protocol 1.2"""

    CLIENT_NAME = "legacy"
    CLIENT_VERSION = __version__

    def __init__(
        self, name: str, username: str, password_hash: str, handshake_url: str
    ):
        """
        Creates a LegacyScrobbler object.

        :param name: String. Name of the scrobbler network.
        :param username: String. Name of the user on the scrobbler network.
        :param password_hash: String. md5-hashed password of the given user.
            Hash the password before passing it to the constructor. Do not
            give the plaintext password.
        :param handshake_url: String. Url of the handshake endpoint of the
            scrobble service
        """
        super().__init__()

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

    def scrobble(self, listens: Listens):
        """
        Scrobbles the given Listens to the scrobbler service.

        :param listens: Collection of Listen objects
        """
        data = Listen.scrobble_params_many(listens)
        data["s"] = self.session
        PostRequest(self.scrobble_url, data).execute()

    def _execute_request(
        self,
        method: Callable,
        else_cb: Callable = None,
        finally_cb: Callable = None,
        arg: Union[Listens, Listen] = None,
    ):

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
