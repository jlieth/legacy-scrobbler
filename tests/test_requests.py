from typing import Callable
import unittest

import httmock
import requests

from legacy_scrobbler.requests import HandshakeRequest, PostRequest
from legacy_scrobbler.exceptions import (
    HardFailureError,
    RequestsError,
    ClientBannedException,
    BadAuthException,
    BadTimeException,
    BadSessionError,
)


class RequestTests:
    @staticmethod
    def create_callback(content="", status_code=200) -> Callable:
        """
        Wrapper function that returns a function for use as a httmock callback.
        The callback function will return a request with the content and
        status_code given to the wrapper function.

        :param content: Content of the response object of the callback.
        :param status_code: Status code of the response object of the callback.
        :return: The callable function
        """

        @httmock.all_requests
        def inner(url, request):
            return httmock.response(
                content=content, status_code=status_code, request=request
            )

        return inner

    def test_common_exceptions(self):
        """
        Tests that the execute() method raises the appropriate exceptions
        for server responses common to both Request types.

        Conditions tested:
        - RequestsError if requests library raises exception
        - HardFailureError if status code is not 200
        - HardFailureError if the server response is not in protocol
        """
        # RequestsError if requests library raises exception
        @httmock.all_requests
        def raises_requests_exception(url, request):
            raise requests.exceptions.RequestException()

        with httmock.HTTMock(raises_requests_exception):
            self.assertRaises(RequestsError, self.request.execute)

        # HardFailureError if status code is not 200
        callback = self.create_callback(status_code=500)
        with httmock.HTTMock(callback):
            self.assertRaises(HardFailureError, self.request.execute)

        # HardFailureError if the server response is not in protocol
        callback = self.create_callback(content="foobar")
        with httmock.HTTMock(callback):
            self.assertRaises(HardFailureError, self.request.execute)


class HandshakeRequestTests(RequestTests, unittest.TestCase):
    """Tests for legacy_scrobbler.requests.HandshakeRequest"""

    def setUp(self):
        self.request = HandshakeRequest(
            url="http://doesntmatter.com", params={"what": "ever"}
        )

    def test_handshake_request_on_success(self):
        """
        Tests HandshakeRequest.execute() with a successful handshake as server
        response. Should return the session_id, nowplaying_url and scrobble_url
        received from the server.
        """
        # create callback with the a bogus (but successful) response
        response_content = "OK\nsessionid\nnowplaying_url\nscrobble_url\n"
        callback = self.create_callback(response_content)

        # mock the request
        with httmock.HTTMock(callback):
            result = self.request.execute()

        # result should contain the response_content defined above
        self.assertEqual(result[0], "sessionid")
        self.assertEqual(result[1], "nowplaying_url")
        self.assertEqual(result[2], "scrobble_url")

    def test_exceptions(self):
        """
        Tests that HandshakeRequest.execute() raises the appropriate exceptions
        for different server responses.

        Conditions tested:
        - ClientBannedException on server response "BANNED"
        - BadAuthException on server response "BADAUTH"
        - BadTimeException on server response "BADTIME"
        """
        # ClientBannedException on server response "BANNED"
        callback = self.create_callback(content="BANNED")
        with httmock.HTTMock(callback):
            self.assertRaises(ClientBannedException, self.request.execute)

        # BadAuthException on server response "BADAUTH"
        callback = self.create_callback(content="BADAUTH")
        with httmock.HTTMock(callback):
            self.assertRaises(BadAuthException, self.request.execute)

        # BadTimeException on server response "BADTIME"
        callback = self.create_callback(content="BADTIME")
        with httmock.HTTMock(callback):
            self.assertRaises(BadTimeException, self.request.execute)


class PostRequestTests(RequestTests, unittest.TestCase):
    """Tests for legacy_scrobbler.requests.PostRequest"""

    def setUp(self):
        self.request = PostRequest(url="http://doesntmatter.com", data={"what": "ever"})

    def test_post_request_on_success(self):
        """
        Tests PostRequest.execute() with a server response indicating success.
        Should return the session_id, nowplaying_url and scrobble_url
        received from the server.
        """
        pass

    def test_exceptions(self):
        """
        Tests that PostRequest.execute() raises the appropriate exceptions
        for different server responses.

        Conditions tested:
        - BadSessionError on server response "BADSESSION"
        """

        # BadSessionError on server response "BADSESSION"
        callback = self.create_callback(content="BADSESSION")
        with httmock.HTTMock(callback):
            self.assertRaises(BadSessionError, self.request.execute)
