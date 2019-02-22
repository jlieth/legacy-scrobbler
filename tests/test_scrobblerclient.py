from collections import deque
import datetime
import random
import unittest
from unittest.mock import patch, Mock, PropertyMock

from legacy_scrobbler.client import ScrobblerClient
from legacy_scrobbler.listen import Listen
from legacy_scrobbler.exceptions import (
    HardFailureError,
    RequestsError,
    BadSessionError,
    HandshakeError,
    SubmissionWithoutListensError,
)


class ScrobblerClientTests(unittest.TestCase):
    """Tests for legavy_scrobbler.client.ScrobblerClient"""

    def setUp(self):
        # create client
        self.client = ScrobblerClient(
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

    def test_enqueue(self):
        """
        Tests legacy_scrobbler.client.ScrobblerClient.enqueue_listens()

        Uses some listens from self.listens as initial queue, shuffles the
        list of other listens and calls enqueue_listens() with the shuffled
        list. Resulting queue should be in chronological order (same as
        self.listens, just as a deque).
        """
        # initialize queue as [2, 4] (indices are of course zero-indexed)
        queue = [self.listens[1], self.listens[3]]
        self.client.queue = deque(queue)

        # enqueue other listens in order [3, 5, 1]
        others = [self.listens[0], self.listens[2], self.listens[4]]
        random.shuffle(others)
        self.client.enqueue_listens(others)

        # queue should be in same order [1, 2, 3, 4, 5] as self.listens now
        self.assertEqual(self.client.queue, deque(self.listens))

    @patch.object(ScrobblerClient, "_in_case_of_failure")
    @patch.object(ScrobblerClient, "handshake")
    def test_execute_handshake(self, mocked_handshake, mocked_in_case_of_failure):
        """
        Tests legacy_scrobbler.client.ScrobblerClient._execute_request()

        The method ScrobblerClient._in_case_of_failure() is used a couple of
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

    def test_allowed_to_handshake(self):
        """
        Tests legacy_scrobbler.client.ScrobblerClient._allowed_to_handshake
        in two circumstances:
        - If ScrobblerClient._time_to_next_handshake returns a timedelta
          of zero, _allowed_to_handshake() should return True.
        - If ScrobblerClient._time_to_next_handshake returns a timedelta
          greater than zero, _allowed_to_handshake should return False.

        The test mocks _time_to_next_handshake in order to create the two
        circumstances that should be tested.
        """
        # patch _time_to_next_handshake method to always return a delta of
        # zero. _allowed_to_handshake should return True in this case.
        with patch.object(
            ScrobblerClient,
            "_time_to_next_handshake",
            new_callable=PropertyMock,
            return_value=datetime.timedelta(seconds=0),
        ):
            self.assertTrue(self.client._allowed_to_handshake)

        # patch _time_to_next_handshake method to always return a delta greater
        # than zero. _allowed_to_handshake should return False in this case.
        with patch.object(
            ScrobblerClient,
            "_time_to_next_handshake",
            new_callable=PropertyMock,
            return_value=datetime.timedelta(seconds=100),
        ):
            self.assertFalse(self.client._allowed_to_handshake)

    def test_time_to_next_handshake(self):
        """
        Tests legacy_scrobbler.client.ScrobblerClient._test_time_to_next_handshake
        for the four possible expected outcomes:
        - If no delay is set in the client, the method should return a timedelta
          of zero
        - If no handshake has happened yet, even if a delay is set, the method
          should return a timedelta of zero
        - If a delay is set and the timestamp of a previous handshake is saved,
          the method should return a timedelta of zero if the last handshake
          was longer ago than the current delay
        - If a delay is set and the timestamp of a previous handshake is saved,
          the method should return a positive timedelta (the remaining time
          that has to pass until a handshake attempt may be made)
        """
        # timedelta on no delay should be zero
        self.client.delay = 0
        self.assertEqual(
            self.client._time_to_next_handshake, datetime.timedelta(seconds=0)
        )

        # timedelta on no last_handshake should be zero
        self.client.delay = 8 * 60
        self.client.last_handshake = None
        self.assertEqual(
            self.client._time_to_next_handshake, datetime.timedelta(seconds=0)
        )

        # test with a delay of eight minutes and last_handshake ten minutes
        # ago. Delay has passed so result should be a zero timedelta
        now = datetime.datetime.now(datetime.timezone.utc)
        self.client.last_handshake = now - datetime.timedelta(minutes=10)
        self.assertEqual(
            self.client._time_to_next_handshake, datetime.timedelta(seconds=0)
        )

        # test with a delay of eight minutes and last timestamp 4 mins 40 secs
        # ago. Expected value is a timedelta of 3 mins 20 secs. However, the
        # function call takes som microseconds so the actual value will be
        # slightly smaller. Actual value should be between 3:19.9 and 3:20
        self.client.last_handshake = now - datetime.timedelta(minutes=4, seconds=40)
        actual = self.client._time_to_next_handshake
        lower_bound = datetime.timedelta(minutes=3, seconds=19.9)
        upper_bound = datetime.timedelta(minutes=3, seconds=20)
        self.assertTrue(lower_bound <= actual <= upper_bound)

    def test_sort_queue(self):
        """Tests legacy_scrobbler.client.ScrobblerClient._sort_queue()"""
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
        Test legacy_scrobbler.client.ScrobblerClient._in_case_of_failure()

        The method should:
        - increase failure counter
        - call ScrobblerClient._increase_delay()
        - set internal state to "no_session" if failure counter >= 3
        """
        # assert initial state of zero failures, zero delay
        self.assertEqual(self.client.hard_fails, 0)
        self.assertEqual(self.client.delay, 0)

        # should increase failure counter
        self.client._in_case_of_failure()
        self.assertEqual(self.client.hard_fails, 1)

        # should call _increase_delay()
        # mocking _increase_delay to assure that it was called
        with patch.object(ScrobblerClient, "_increase_delay") as mock_method:
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
        self.client.delay = 0

    def test_increase_delay(self):
        """
        Tests legacy_scrobbler.client.ScrobblerClient._increase_delay()

        Per protocol: "If a hard failure occurs at the handshake phase, the
        client should initially pause for 1 minute before handshaking again.
        Subsequent failed handshakes should double this delay up to a maximum
        delay of 120 minutes."
        https://www.last.fm/api/submissions
        """
        # delay should be zero in the beginning
        self.assertEqual(self.client.delay, 0)

        # increasing the delay should first result in one minute delay and
        # then double with every increase
        for minute in [1, 2, 4, 8, 16, 32, 64]:
            self.client._increase_delay()
            self.assertEqual(self.client.delay, minute * 60)

        # up to 120 minutes max
        self.client._increase_delay()
        self.assertEqual(self.client.delay, 120 * 60)
        self.client._increase_delay()
        self.assertEqual(self.client.delay, 120 * 60)

        # reset delay to zero
        self.client.delay = 0
