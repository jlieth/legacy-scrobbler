import hashlib
import time

import requests

from legacy_scrobbler.exceptions import (
    BadSessionError,
    HandshakeError,
    HardFailureError,
    SubmissionWithoutListensError,
)
from legacy_scrobbler.listen import Listen
from legacy_scrobbler.version import __version__


class Network:
    CLIENT_NAME = "legacy"
    CLIENT_VERSION = __version__

    def __init__(
        self, name: str, username: str, password_hash: str, handshake_url: str
    ):
        self.name = name
        self.username = username
        self.password_hash = password_hash.encode("utf-8")
        self.handshake_url = handshake_url

        self.nowplaying_url = None
        self.submission_url = None
        self.session = None

    def handshake(self):
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

        r = requests.get(self.handshake_url, params=params)
        self.process_handshake_response(r)

    def nowplaying(self, listen: Listen):
        if self.session is None:
            raise BadSessionError("No session exists")

        params = listen.nowplaying_params()
        params["s"] = self.session

        r = requests.post(self.nowplaying_url, data=params)
        self.process_post_response(r)

    def submit(self, *listens: Listen):
        if self.session is None:
            raise BadSessionError("No session exists")

        if len(listens) == 0:
            raise SubmissionWithoutListensError()

        params = {"s": self.session}
        for i, listen in enumerate(listens):
            submit_params = listen.submit_params(idx=i)
            params.update(submit_params)

        r = requests.post(self.submission_url, data=params)
        self.process_post_response(r)

    def process_handshake_response(self, r):
        is_hard_failure = not r.status_code == requests.codes.ok
        if is_hard_failure:
            raise HardFailureError(r.status_code)

        result = r.text.split("\n")
        if len(result) >= 4 and result[0] == "OK":
            self.session = result[1]
            self.nowplaying_url = result[2]
            self.submission_url = result[3]
            return
        elif result[0] == "BANNED":
            msg = "The scrobbler client is banned from this network."
            raise HandshakeError(msg)
        elif result[0] == "BADAUTH":
            msg = "Authentication failed. Check credentials and try again."
            raise HandshakeError(msg)
        elif result[0] == "BADTIME":
            msg = "Reported timestamp is off. Check your system clock."
            raise HandshakeError(msg)
        else:
            raise HardFailureError(r.text)

    def process_post_response(self, r):
        is_hard_failure = not r.status_code == requests.codes.ok
        if is_hard_failure:
            raise HardFailureError(r.status_code)

        if r.text.startswith("OK"):
            return
        elif r.text.startswith("BADSESSION"):
            raise BadSessionError()
        else:
            raise HardFailureError(r.text)
