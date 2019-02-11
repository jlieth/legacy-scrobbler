import datetime
import hashlib
import unittest
from urllib.parse import urlparse, parse_qs, unquote
from typing import Callable

import httmock

from legacy_scrobbler.listen import Listen
from legacy_scrobbler import Network
from legacy_scrobbler.exceptions import (
    HardFailureError,
    HandshakeError,
    BadSessionError,
    SubmissionWithoutListensError,
)


class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.network = Network(
            name="ScrobblerNetwork",
            username="testuser",
            password_hash="3858f62230ac3c915f300c664312c63f",
            handshake_url="http://somescrobblernetwork.com/handshake",
        )

    @staticmethod
    def simple_request_callback(content="", status_code=200) -> Callable:
        @httmock.all_requests
        def inner(url, request):
            return httmock.response(
                content=content, status_code=status_code, request=request
            )

        return inner

    @staticmethod
    def required_params_present(required: list, received: list) -> bool:
        return False not in [x in received for x in required]


class HandshakeTests(NetworkTests):
    def test_handshake_request(self):
        @httmock.all_requests
        def validate_handshake(url, request):
            # method == GET
            self.assertEqual(request.method, "GET")

            query_params = parse_qs(urlparse(request.url).query)

            # all required params present
            required = ["hs", "p", "c", "v", "u", "t", "a"]
            received = query_params.keys()
            self.assertTrue(self.required_params_present(required, received))

            # only one value per key
            for key, val in query_params.items():
                self.assertEqual(len(val), 1)
                query_params[key] = val[0]

            # check query params
            self.assertEqual(query_params["hs"], "true")
            self.assertEqual(query_params["p"], "1.2")
            self.assertEqual(query_params["c"], self.network.CLIENT_NAME)
            self.assertEqual(query_params["v"], self.network.CLIENT_VERSION)
            self.assertEqual(query_params["u"], "testuser")
            self.assertTrue(query_params["t"].isnumeric())

            # calculate expected auth and compare to submitted auth
            timestamp = query_params["t"].encode("utf-8")
            password_hash = "3858f62230ac3c915f300c664312c63f".encode("utf-8")
            auth = hashlib.md5(password_hash + timestamp).hexdigest()
            self.assertEqual(query_params["a"], auth)

            content = "OK\nsession\nurl\nurl\n"
            return httmock.response(content=content, status_code=200, request=request)

        with httmock.HTTMock(validate_handshake):
            self.network.handshake()

    def test_handshake_response_processing_on_success(self):
        response_content = "OK\nsessionid\nnowplaying_url\nsubmission_url\n"
        callback = self.simple_request_callback(response_content)
        with httmock.HTTMock(callback):
            self.network.handshake()

        self.assertEqual(self.network.session, "sessionid")
        self.assertEqual(self.network.nowplaying_url, "nowplaying_url")
        self.assertEqual(self.network.submission_url, "submission_url")

    def test_handshake_response_processing_on_hard_failure(self):
        with httmock.HTTMock(self.simple_request_callback(status_code=500)):
            self.assertRaises(HardFailureError, self.network.handshake)

    def test_handshake_response_processing_on_banned(self):
        callback = self.simple_request_callback(content="BANNED")
        with httmock.HTTMock(callback):
            self.assertRaises(HandshakeError, self.network.handshake)

    def test_handshake_response_processing_on_badauth(self):
        callback = self.simple_request_callback(content="BADAUTH")
        with httmock.HTTMock(callback):
            self.assertRaises(HandshakeError, self.network.handshake)

    def test_handshake_response_processing_on_badtime(self):
        callback = self.simple_request_callback(content="BADTIME")
        with httmock.HTTMock(callback):
            self.assertRaises(HandshakeError, self.network.handshake)

    def test_handshake_response_processing_on_other_response(self):
        callback = self.simple_request_callback(content="foobar")
        with httmock.HTTMock(callback):
            self.assertRaises(HardFailureError, self.network.handshake)


class PostRequestTests(NetworkTests):
    def setUp(self):
        super().setUp()

        # set values on network usually received during handshake
        self.session = "fakesession"
        self.nowplaying_url = "http://somescrobblernetwork.com/nowplaying"
        self.submission_url = "http://somescrobblernetwork.com/submission"
        self.network.session = self.session
        self.network.nowplaying_url = self.nowplaying_url
        self.network.submission_url = self.submission_url

        # create Listen objects
        self.date = datetime.datetime.now(datetime.timezone.utc)
        self.listens = [
            Listen(
                date=self.date,
                artist_name="アーティスト",
                track_title="трек",
                album_title="Αλμπουμ",
                length=100,
                tracknumber=1,
                mb_trackid="जो कुछ",
                source="P",
                rating="L",
            ),
            Listen(
                date=self.date + datetime.timedelta(seconds=100),
                artist_name="Nghệ sĩ",
                track_title="跟踪",
                album_title="앨범",
                length=100,
                tracknumber=1,
                mb_trackid="যাই হোক",
                source="P",
                rating="L",
            ),
            Listen(
                date=self.date + datetime.timedelta(seconds=200),
                artist_name="Artist",
                track_title="Track",
                album_title="Album",
                length=100,
                tracknumber=1,
                mb_trackid="whatever",
                source="P",
                rating="L",
            ),
        ]


class NowplayingTests(PostRequestTests):
    def test_nowplaying_request(self):
        @httmock.all_requests
        def validate_nowplaying(url, request):
            # method == POST
            self.assertEqual(request.method, "POST")

            # request body is utf-8 encoded
            unquote(request.body, encoding="utf-8", errors="strict")

            query_params = parse_qs(request.body)

            # all required params present
            required = ["s", "a", "t", "b", "l", "n", "m"]
            received = query_params.keys()
            self.assertTrue(self.required_params_present(required, received))

            # only one value per key
            for key, val in query_params.items():
                self.assertEqual(len(val), 1)
                query_params[key] = val[0]

            # check query params
            listen = self.listens[0]
            self.assertEqual(query_params["s"], self.session)
            self.assertEqual(query_params["a"], listen.artist_name)
            self.assertEqual(query_params["t"], listen.track_title)
            self.assertEqual(query_params["b"], listen.album_title)
            self.assertEqual(query_params["l"], str(listen.length))
            self.assertEqual(query_params["n"], str(listen.tracknumber))
            self.assertEqual(query_params["m"], listen.mb_trackid)

            return httmock.response(content="OK\n", status_code=200, request=request)

        with httmock.HTTMock(validate_nowplaying):
            self.network.nowplaying(self.listens[0])

    def test_nowplaying_without_session(self):
        listen = self.listens[0]
        self.network.session = None
        self.assertRaises(BadSessionError, self.network.nowplaying, listen)
        self.network.session = self.session

    def test_nowplaying_response_processing_on_hard_failure(self):
        with httmock.HTTMock(self.simple_request_callback(status_code=500)):
            listen = self.listens[0]
            self.assertRaises(HardFailureError, self.network.nowplaying, listen)

    def test_nowplaying_response_processing_on_badsession(self):
        callback = self.simple_request_callback(content="BADSESSION")
        with httmock.HTTMock(callback):
            listen = self.listens[0]
            self.assertRaises(BadSessionError, self.network.nowplaying, listen)

    def test_nowplaying_response_processing_on_other_response(self):
        callback = self.simple_request_callback(content="foobar")
        with httmock.HTTMock(callback):
            listen = self.listens[0]
            self.assertRaises(HardFailureError, self.network.nowplaying, listen)


class SubmitTests(PostRequestTests):
    @staticmethod
    def build_list_of_required_params(num_listens):
        base_params = [
            "a[%i]",
            "t[%i]",
            "i[%i]",
            "o[%i]",
            "r[%i]",
            "l[%i]",
            "b[%i]",
            "n[%i]",
            "m[%i]",
        ]

        params = []
        for i in range(num_listens):
            for param in base_params:
                params.append(param % i)
        return params

    def _test_submit_request(self):
        @httmock.all_requests
        def validate_submit(url, request):
            # method == POST
            self.assertEqual(request.method, "POST")

            # request body is utf-8 encoded
            unquote(request.body, encoding="utf-8", errors="strict")

            query_params = parse_qs(request.body)

            # all required params present
            num_listens = len(self.listens)
            required = self.build_list_of_required_params(num_listens)
            required += "s"
            received = query_params.keys()
            self.assertTrue(self.required_params_present(required, received))

            # only one value per key
            for key, val in query_params.items():
                self.assertEqual(len(val), 1)
                query_params[key] = val[0]

            # check query params
            self.assertEqual(query_params["s"], self.session)

            for i in range(num_listens):
                listen = self.listens[i]
                self.assertEqual(query_params["a[%i]" % i], listen.artist_name)
                self.assertEqual(query_params["t[%i]" % i], listen.track_title)
                self.assertEqual(query_params["i[%i]" % i], listen.timestamp)
                self.assertEqual(query_params["o[%i]" % i], listen.source)
                self.assertEqual(query_params["r[%i]" % i], listen.rating)
                self.assertEqual(query_params["l[%i]" % i], str(listen.length))
                self.assertEqual(query_params["b[%i]" % i], listen.album_title)
                self.assertEqual(query_params["n[%i]" % i], str(listen.tracknumber))
                self.assertEqual(query_params["m[%i]" % i], listen.mb_trackid)

            return httmock.response(content="OK\n", status_code=200, request=request)

        with httmock.HTTMock(validate_submit):
            self.network.nowplaying(*self.listens)

    def test_submit_without_session(self):
        self.network.session = None
        self.assertRaises(BadSessionError, self.network.submit, *self.listens)
        self.network.session = self.session

    def test_submit_without_listens(self):
        self.assertRaises(SubmissionWithoutListensError, self.network.submit)

    def test_submit_response_processing_on_hard_failure(self):
        with httmock.HTTMock(self.simple_request_callback(status_code=500)):
            self.assertRaises(HardFailureError, self.network.submit, *self.listens)

    def test_submit_response_processing_on_badsession(self):
        callback = self.simple_request_callback(content="BADSESSION")
        with httmock.HTTMock(callback):
            self.assertRaises(BadSessionError, self.network.submit, *self.listens)

    def test_submit_response_processing_on_other_response(self):
        callback = self.simple_request_callback(content="foobar")
        with httmock.HTTMock(callback):
            self.assertRaises(HardFailureError, self.network.submit, *self.listens)
