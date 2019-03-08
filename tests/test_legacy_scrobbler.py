from collections import deque
import datetime
import random
import unittest
from unittest.mock import patch, Mock, PropertyMock

from legacy_scrobbler.clients import interface
from legacy_scrobbler.clients.legacy import LegacyScrobbler
from legacy_scrobbler.listen import Listen
from legacy_scrobbler.exceptions import (
    HardFailureError,
    RequestsError,
    BadSessionError,
    HandshakeError,
    SubmissionWithoutListensError,
)


class ScrobblerClientTests(unittest.TestCase):
    """Tests for legacy_scrobbler.client.LegacyScrobbler"""

    def setUp(self):
        # create client
        self.client = LegacyScrobbler(
            name="ScrobblerNetwork",
            username="testuser",
            password_hash="3858f62230ac3c915f300c664312c63f",
            handshake_url="http://somescrobblernetwork.com/handshake",
        )

        # create some listens for later
        # list is chronological
        now = datetime.datetime.now(datetime.timezone.utc)
        self.listens = [
            Listen(
                date=now - datetime.timedelta(minutes=10),
                artist_name="Artist1",
                track_title="Track2",
            ),
            Listen(
                date=now - datetime.timedelta(minutes=8),
                artist_name="Artist3",
                track_title="Track4",
            ),
            Listen(
                date=now - datetime.timedelta(minutes=6),
                artist_name="Artist5",
                track_title="Track6",
            ),
            Listen(
                date=now - datetime.timedelta(minutes=4),
                artist_name="Artist7",
                track_title="Track8",
            ),
            Listen(
                date=now - datetime.timedelta(minutes=2),
                artist_name="Artist9",
                track_title="Track10",
            ),
        ]

    @patch.object(interface.Delay, "is_active", new_callable=PropertyMock)
    @patch.object(LegacyScrobbler, "_execute_request")
    def test_tick(self, mocked_execute_request: Mock, mocked_is_active: Mock):
        """
        Tests legacy_scrobbler.client.LegacyScrobbler.tick()

        The property legacy_scrobbler.delay.Delay.is_active is mocked during
        this test to simulate a specific program state.

        The method LegacyScrobbler._execute_request() is mocked during this
        test to determine if tick() has called the method and which arguments
        were given to it.

        Situations tested:
        - if self.state is "no_session" but delay.is_active returns
          True, nothing should happen (that is, _execute_request should not
          be called)
        - if self.state is "idle" and neither self.np is set nor self.queue
          contains any listens, nothing should happen (that is,
          _execute_request should not be called)
        - if self.state is "no_session" and delay.is_active returns False,
          execute_request should be called with the arguments:
            method=self.handshake
            else_cb=self.on_successful_handshake_cb
            finally_cb=self.on_handshake_attempt_cb
        - if self.state is "idle" and self.np is set, _execute_request should
          be called with the arguments:
            method=self.nowplaying
            else_cb=self.on_successful_nowplaying_cb
            arg=self.np
        - if self.state is "idle" and self.queue contains listens,
          _execute_request should be called with the arguments:
            method=self.scrobble
            else_cb=self.on_successful_scrobble_cb
            arg=deque(list(self.queue)[:50])


        :param mocked_execute_request: Mock method of _execute_request
        :param mocked_is_active: Mock method of delay.is_active
        """

        # if self.state is "no_session" but delay.is_active returns
        # True, nothing should happen (that is, _execute_request should not
        # be called)
        self.client.state = "no_session"
        mocked_is_active.return_value = True
        self.client.tick()
        mocked_execute_request.assert_not_called()

        # if self.state is "idle" and neither self.np is set nor self.queue
        # contains any listens, nothing should happen (that is,
        # _execute_request should not be called)
        self.client.state = "idle"
        self.client.np = None
        self.client.queue.clear()
        self.client.tick()
        mocked_execute_request.assert_not_called()

        # if self.state is "no_session" and delay.is_active returns False,
        # execute_request should be called with the arguments:
        #   method=self.handshake
        #   else_cb=self.on_successful_handshake_cb
        #   finally_cb=self.on_handshake_attempt_cb
        self.client.state = "no_session"
        mocked_is_active.return_value = False
        self.client.tick()
        mocked_execute_request.assert_called_with(
            method=self.client.handshake,
            else_cb=self.client.on_successful_handshake_cb,
            finally_cb=self.client.on_handshake_attempt_cb,
        )
        mocked_execute_request.reset_mock()

        # if self.state is "idle" and self.np is set, _execute_request should
        # be called with the arguments:
        #   method=self.nowplaying
        #   else_cb=self.on_successful_nowplaying_cb
        #   arg=self.np
        self.client.state = "idle"
        self.client.np = self.listens[0]
        self.client.tick()
        mocked_execute_request.assert_called_with(
            method=self.client.nowplaying,
            else_cb=self.client.on_successful_nowplaying_cb,
            arg=self.client.np,
        )
        # unset self.client.np
        self.client.np = None

        # if self.state is "idle" and self.queue contains listens,
        # _execute_request should be called with the arguments:
        #   method=self.scrobble
        #   else_cb=self.on_successful_scrobble_cb
        #   arg=deque(list(self.queue)[:50])
        self.client.state = "idle"
        self.client.add_listens(self.listens)
        self.client.tick()
        mocked_execute_request.assert_called_with(
            method=self.client.scrobble,
            else_cb=self.client.on_successful_scrobble_cb,
            arg=deque(list(self.client.queue)[:50]),
        )

    def test_set_nowplaying(self):
        """Tests legacy_scrobbler.client.LegacyScrobbler.send_nowplaying()"""
        self.client.send_nowplaying(self.listens[0])
        self.assertEqual(self.client.np, self.listens[0])

        # unset np
        self.client.np = None

    def test_enqueue(self):
        """
        Tests legacy_scrobbler.client.LegacyScrobbler.add_listens()

        Uses some listens from self.listens as initial queue, shuffles the
        list of other listens and calls add_listens() with the shuffled
        list. Resulting queue should be in chronological order (same as
        self.listens, just as a deque).
        """
        # initialize queue as [2, 4] (indices are of course zero-indexed)
        queue = [self.listens[1], self.listens[3]]
        self.client.queue = deque(queue)

        # enqueue other listens in order [3, 5, 1]
        others = [self.listens[0], self.listens[2], self.listens[4]]
        random.shuffle(others)
        self.client.add_listens(others)

        # queue should be in same order [1, 2, 3, 4, 5] as self.listens now
        self.assertEqual(self.client.queue, deque(self.listens))

    @patch.object(LegacyScrobbler, "_in_case_of_failure")
    @patch.object(LegacyScrobbler, "handshake")
    def test_execute_handshake(self, mocked_handshake, mocked_in_case_of_failure):
        """
        Tests legacy_scrobbler.client.LegacyScrobbler._execute_request()

        The method LegacyScrobbler._in_case_of_failure() is used a couple of
        times during _execute_request() and is being mocked during this test
        in order to check that it actually is being called.

        _execute_request() takes a callable as its first argument. The argument
        function is used to make the actual request. The argument callable can
        only be handshake, nowplaying or scrobble. During this test, the
        argument function needs to be a dummy function so we can determine
        the desired behaviour. However, since the input callable needs to be
        one of the mentioned methods, we'll need to mock one of those functions
        instead of just passing in a dummy function.

        Situations tested:
        - if the input callable raises a HardFailureError, _in_case_of_failure
          should be called
        - if the input callable raises a RequestsError, _in_case_of_failure
          should be called
        - if the input callable raises a BadSessionError, session should be
          unset and state set to "no_session"
        - if the input callable raises a HandshakeError, the same error should
          be re-raised
        - if the input callable raises a SubmissionWithoutListensError, the
          same error should be re-raised
        - on a successful request, the else_cb should be called
        - on an unsuccessful request, the else_cb should not be called
        - the finally_cb should be called on both a successful and an
          unsuccessful request

        :param mocked_handshake: Mock method of handshake
        :param mocked_in_case_of_failure: Mock method of _in_case_of_failure()
        """
        # we have to set function __name__ on the mocked handshake
        mocked_handshake.__name__ = "handshake"

        # if the input callable raises a HardFailureError, _in_case_of_failure
        # should be called
        mocked_handshake.side_effect = HardFailureError()
        self.client._execute_request(method=self.client.handshake)
        mocked_in_case_of_failure.assert_called()
        mocked_in_case_of_failure.reset_mock()

        # if the input callable raises a RequestsError, _in_case_of_failure
        # should be called
        mocked_handshake.side_effect = RequestsError()
        self.client._execute_request(method=self.client.handshake)
        mocked_in_case_of_failure.assert_called()
        mocked_in_case_of_failure.reset_mock()

        # if the input callable raises a BadSessionError, session should be
        # unset and state set to "no_session"
        mocked_handshake.side_effect = BadSessionError()
        self.client._execute_request(method=self.client.handshake)
        self.assertIsNone(self.client.session)
        self.assertEqual(self.client.state, "no_session")

        # if the input callable raises a HandshakeError, the same error should
        # be re-raised
        mocked_handshake.side_effect = HandshakeError()
        self.assertRaises(
            HandshakeError, self.client._execute_request, method=self.client.handshake
        )

        # if the input callable raises a SubmissionWithoutListensError, the
        # same error should be re-raised
        mocked_handshake.side_effect = SubmissionWithoutListensError()
        self.assertRaises(
            SubmissionWithoutListensError,
            self.client._execute_request,
            method=self.client.handshake,
        )

        # on a successful request, the else_cb should be called
        else_cb = Mock()
        mocked_handshake.side_effect = None
        self.client._execute_request(method=self.client.handshake, else_cb=else_cb)
        else_cb.assert_called()

        # on an unsuccessful request, the else_cb should not be called
        else_cb = Mock()
        mocked_handshake.side_effect = HardFailureError()
        self.client._execute_request(method=self.client.handshake, else_cb=else_cb)
        else_cb.assert_not_called()

        # the finally_cb should be called on both a successful and an
        # unsuccessful request
        finally_cb = Mock()
        mocked_handshake.side_effect = None
        self.client._execute_request(
            method=self.client.handshake, finally_cb=finally_cb
        )
        finally_cb.assert_called()
        finally_cb.reset_mock()

        mocked_handshake.side_effect = HardFailureError()
        self.client._execute_request(
            method=self.client.handshake, finally_cb=finally_cb
        )
        finally_cb.assert_called()

    def test_sort_queue(self):
        """Tests legacy_scrobbler.client.LegacyScrobbler._sort_queue()"""
        # set the shuffled self.listens as queue
        queue = self.listens[:]
        random.shuffle(queue)
        self.client.queue = deque(queue)

        # queue should be in same order as self.listens after sorting (but a deque)
        self.client._sort_queue()
        expected = deque(self.listens)
        self.assertEqual(self.client.queue, expected)

    def test_in_case_of_failure(self):
        """
        Test legacy_scrobbler.client.LegacyScrobbler._in_case_of_failure()

        The method should:
        - increase failure counter
        - call legacy_scrobbler.delay.Delay.increase()
        - set internal state to "no_session" if failure counter >= 3
        """
        # assert initial state of zero failures, zero delay
        self.assertEqual(self.client.hard_fails, 0)
        self.assertEqual(self.client.delay._seconds, 0)

        # should increase failure counter
        self.client._in_case_of_failure()
        self.assertEqual(self.client.hard_fails, 1)

        # should call _increase_delay()
        # mocking _increase_delay to assure that it was called
        with patch.object(interface.Delay, "increase") as mock_method:
            self.client._in_case_of_failure()
            mock_method.assert_called()

        # should set internal state to "no_session" if failure counter >= 3
        # setting initial state to something else
        self.client.state = "idle"
        self.client.hard_fails = 23
        self.client._in_case_of_failure()
        self.assertEqual(self.client.state, "no_session")

        # reset
        self.client.hard_fails = 0
        self.client.delay.reset()
