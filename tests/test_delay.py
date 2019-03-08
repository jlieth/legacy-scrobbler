import datetime
import unittest
from unittest.mock import patch, PropertyMock

from legacy_scrobbler.delay import Delay


class DelayTests(unittest.TestCase):
    """Tests for legacy_scrobbler.delay.Delay"""

    def setUp(self):
        self.delay = Delay(
            options={
                "base": 60,  # 1 minute base
                "max": 7200,  # 120 minutes max
                "multiplier": 2,
            }
        )

    def test_start(self):
        """Tests legacy_scrobbler.delay.Delay.start()"""
        # call start
        self.delay.start()

        # start() should set _start_time to now, though we have to test for an
        # interval since a bit of time passes between the call and now
        now = datetime.datetime.now(datetime.timezone.utc)
        lower = now - datetime.timedelta(seconds=0.1)
        upper = now + datetime.timedelta(seconds=0.1)
        self.assertTrue(lower <= self.delay._start_time <= upper)

        # start() calls increase(), therefore _seconds should be base delay
        base_delay = self.delay._options["base"]
        self.assertEqual(self.delay._seconds, base_delay)

    def test_reset(self):
        """Tests legacy_scrobbler.delay.Delay.reset()"""
        # set a start time and a delay
        self.delay._start_time = datetime.datetime.now(datetime.timezone.utc)
        self.delay._seconds = 200

        # call reset. seconds and start time should be 0 and None, respectively
        self.delay.reset()
        self.assertEqual(self.delay._start_time, None)
        self.assertEqual(self.delay._seconds, 0)

    def test_is_active(self):
        """
        Tests legacy_scrobbler.delayDelay._is_active
        in two circumstances:
        - If Delay.remaining returns a timedelta of zero, Delay.is_active
          should return False.
        - If Delay.remaining returns a timedelta greater than zero,
          Delay.is_active should return True.

        The test mocks Delay.remaining in order to create the two
        circumstances that should be tested.
        """
        # patch Delay.remaining method to always return a delta of
        # zero. Delay.is_active should return False in this case.
        with patch.object(
            Delay,
            "remaining",
            new_callable=PropertyMock,
            return_value=datetime.timedelta(seconds=0),
        ):
            self.assertFalse(self.delay.is_active)

        # patch _time_to_next_handshake method to always return a delta greater
        # than zero. _allowed_to_handshake should return False in this case.
        with patch.object(
            Delay,
            "remaining",
            new_callable=PropertyMock,
            return_value=datetime.timedelta(seconds=100),
        ):
            self.assertTrue(self.delay.is_active)

    def test_remaining(self):
        """
        Tests legacy_scrobbler.delay.Delay.remaining for the four possible
        expected outcomes:
        - If no delay is set, the method should return a timedelta of zero
        - If no start time is set, even if a delay is set, the method should
          return a timedelta of zero
        - If both a delay and a start time are set, the method should return a
          timedelta of zero if more than the delay time have passed since the
          start time
        - If both a delay and a start time are set, the method should return a
          positive timedelta if not enough time has passed since the start
          time. The remaining time should be start time + delay - now.
        """
        # timedelta on no delay should be zero
        self.delay._seconds = 0
        self.assertEqual(self.delay.remaining, datetime.timedelta(seconds=0))

        # timedelta on no start time should be zero
        self.delay._seconds = 8 * 60
        self.delay._start_time = None
        self.assertEqual(self.delay.remaining, datetime.timedelta(seconds=0))

        # test with a delay of eight minutes and start time ten minutes
        # ago. Delay has passed so result should be a zero timedelta
        now = datetime.datetime.now(datetime.timezone.utc)
        self.delay._start_time = now - datetime.timedelta(minutes=10)
        self.assertEqual(self.delay.remaining, datetime.timedelta(seconds=0))

        # test with a delay of eight minutes and start time 4 mins 40 secs
        # ago. Expected value is a timedelta of 3 mins 20 secs. However, the
        # function call takes som microseconds so the actual value will be
        # slightly smaller. Actual value should be between 3:19.9 and 3:20
        self.delay._start_time = now - datetime.timedelta(minutes=4, seconds=40)
        remaining = self.delay.remaining
        lower_bound = datetime.timedelta(minutes=3, seconds=19.9)
        upper_bound = datetime.timedelta(minutes=3, seconds=20)
        self.assertTrue(lower_bound <= remaining <= upper_bound)

    def test_increase(self):
        """
        Tests legacy_scrobbler.delay.Delay.increase()

        If the delay is zero, the first increase should set the delay to
        the base delay. Every increase afterwards should increase the delay
        to base_delay * multiplier^num_increase. The delay should be capped
        at max_delay.
        """
        # set delay to 0
        self.delay._seconds = 0

        # grab options
        base_delay = self.delay._options["base"]
        max_delay = self.delay._options["max"]
        multiplier = self.delay._options["multiplier"]

        # increase the delay as long as it is smaller than max_delay
        num_increase = 0
        while self.delay._seconds < max_delay:
            self.delay.increase()
            expected = min(base_delay * multiplier ** num_increase, max_delay)
            self.assertEqual(self.delay._seconds, expected)
            num_increase += 1

        # increasing further should have no effect
        self.delay.increase()
        self.assertEqual(self.delay._seconds, max_delay)
        self.delay.increase()
        self.assertEqual(self.delay._seconds, max_delay)

        # reset delay to zero
        self.delay._seconds = 0
