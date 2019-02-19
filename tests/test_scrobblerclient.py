from collections import deque
import datetime
import unittest
from unittest.mock import patch, PropertyMock

from legacy_scrobbler.client import ScrobblerClient
from legacy_scrobbler.listen import Listen


class ScrobblerClientTests(unittest.TestCase):
    def setUp(self):
        self.client = ScrobblerClient(
            name="ScrobblerNetwork",
            username="testuser",
            password_hash="3858f62230ac3c915f300c664312c63f",
            handshake_url="http://somescrobblernetwork.com/handshake",
        )

    def test_enqueue(self):
        now = datetime.datetime.now(datetime.timezone.utc)

        first = Listen(
            date=now - datetime.timedelta(minutes=10),
            artist_name="Artist",
            track_title="Track",
        )

        second = Listen(
            date=now - datetime.timedelta(minutes=8),
            artist_name="Artist",
            track_title="Track",
        )

        third = Listen(
            date=now - datetime.timedelta(minutes=6),
            artist_name="Artist",
            track_title="Track",
        )

        fourth = Listen(
            date=now - datetime.timedelta(minutes=4),
            artist_name="Artist",
            track_title="Track",
        )

        fifth = Listen(
            date=now - datetime.timedelta(minutes=2),
            artist_name="Artist",
            track_title="Track",
        )

        # initialize queue as [2, 4]
        self.client.queue = deque([second, fourth])

        # enqueue other listens
        self.client.enqueue_listens(third, fifth, first)

        # queue should be [1, 2, 3, 4, 5] now
        self.assertEqual(
            self.client.queue, deque([first, second, third, fourth, fifth])
        )

    def test_allowed_to_handshake(self):
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
        now = datetime.datetime.now(datetime.timezone.utc)

        first = Listen(
            date=now - datetime.timedelta(minutes=100),
            artist_name="Artist",
            track_title="Track",
        )

        second = Listen(
            date=now - datetime.timedelta(minutes=4),
            artist_name="Artist",
            track_title="Track",
        )

        third = Listen(
            date=now + datetime.timedelta(minutes=17),
            artist_name="Artist",
            track_title="Track",
        )

        # queue set as [3, 1, 2]
        self.client.queue = deque([third, first, second])

        # sorting should result in [1, 2, 3]
        self.client._sort_queue()
        self.assertEqual(self.client.queue, deque([first, second, third]))

    def test_increase_delay(self):
        self.assertEqual(self.client.delay, 0)

        # delay should be doubled on every increase
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
