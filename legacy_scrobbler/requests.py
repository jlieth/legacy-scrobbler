import requests

from legacy_scrobbler.exceptions import (
    HardFailureError,
    RequestsError,
    ClientBannedException,
    BadAuthException,
    BadTimeException,
    BadSessionError,
)


class HandshakeRequest:
    def __init__(self, url: str, params: dict, timeout: int = 5):
        self.url = url
        self.params = params
        self.timeout = timeout

    def execute(self):
        """
        Executes the handshake request.

        :raises legacy_scrobbler.exceptions.RequestsError: If the requests
            library raised an exception
        :raises legacy_scrobbler.exceptions.ClientBannedException: If the
            response from the server is "BANNED"
        :raises legacy_scrobbler.exceptions.BadAuthException: If the response
            from the server is "BADAUTH"
        :raises legacy_scrobbler.exceptions.BadTimeException: If the response
            from the server is "BADTIME"
        :raises legacy_scrobbler.exceptions.HardFailureError: If the status
            code of the response isn't 200
        :raises legacy_scrobbler.exceptions.HardFailureError: If the response
            from the server is neither "OK" nor any of the possible errors
            defined above
        """
        # make request
        try:
            r = requests.get(self.url, params=self.params, timeout=self.timeout)
            r.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise HardFailureError(e)
        except requests.exceptions.RequestException as e:
            msg = f"Exception from underlying requests library: {e}"
            raise RequestsError(msg)

        # process response
        result = r.text.split("\n")
        if len(result) >= 4 and result[0] == "OK":
            session = result[1]
            nowplaying_url = result[2]
            scrobble_url = result[3]
            return session, nowplaying_url, scrobble_url
        elif result[0] == "BANNED":
            raise ClientBannedException()
        elif result[0] == "BADAUTH":
            raise BadAuthException()
        elif result[0] == "BADTIME":
            raise BadTimeException()
        else:
            raise HardFailureError(r.text)


class PostRequest:
    def __init__(self, url, data, timeout: int = 5):
        self.url = url
        self.data = data
        self.timeout = timeout

    def execute(self):
        """
        Executes the request.

        :raises legacy_scrobbler.exceptions.RequestsError: If the requests
            library raised an exception
        :raises legacy_scrobbler.exceptions.BadSessionError: If the response
            from the server is "BADSESSION"
        :raises legacy_scrobbler.exceptions.HardFailureError: If the status
            code of the response isn't 200
        :raises legacy_scrobbler.exceptions.HardFailureError: If the response
            from the server is neither "OK" nor "BADSESSION" and thus
            not in the Audioscrobbler protocol.
        """
        # make request
        try:
            r = requests.post(self.url, data=self.data)
            r.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise HardFailureError(e)
        except requests.exceptions.RequestException as e:
            msg = f"Exception from underlying requests library: {e}"
            raise RequestsError(msg)

        # process response
        if r.text.startswith("OK"):
            return
        elif r.text.startswith("BADSESSION"):
            raise BadSessionError("Remote server says the session is invalid")
        else:
            raise HardFailureError(r.text)
