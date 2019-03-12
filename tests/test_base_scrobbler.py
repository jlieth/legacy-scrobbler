from collections import deque
import random
import unittest
from unittest.mock import patch, Mock, PropertyMock

from legacy_scrobbler.clients import base

from .data.listens import listens


class BaseClientTests(unittest.TestCase):
    @patch.multiple(base.ScrobbleClientBase, __abstractmethods__=set())
    def setUp(self):
        self.client = base.ScrobbleClientBase()
        self.listens = listens

    @patch.object(base.Delay, "is_active", new_callable=PropertyMock)
    @patch.object(base.ScrobbleClientBase, "_execute_request")
    def test_tick(self, mocked_execute_request: Mock, mocked_is_active: Mock):
        """
        Tests legacy_scrobbler.client.base.ScrobbleClientBase.tick()

        The property legacy_scrobbler.delay.Delay.is_active is mocked during
        this test to simulate a specific program state.

        The method ScrobbleClientBase._execute_request() is mocked during this
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
            else_cb=self.on_handshake_success
            finally_cb=self.on_handshake
        - if self.state is "idle" and self.np is set, _execute_request should
          be called with the arguments:
            method=self.nowplaying
            else_cb=self.on_nowplaying_success
            arg=self.np
        - if self.state is "idle" and self.queue contains listens,
          _execute_request should be called with the arguments:
            method=self.scrobble
            else_cb=self.on_scrobble_success
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
        #   else_cb=self.on_handshake_success
        #   finally_cb=self.on_handshake
        self.client.state = "no_session"
        mocked_is_active.return_value = False
        self.client.tick()
        mocked_execute_request.assert_called_with(
            method=self.client.handshake,
            else_cb=self.client.on_handshake_success,
            finally_cb=self.client.on_handshake,
        )
        mocked_execute_request.reset_mock()

        # if self.state is "idle" and self.np is set, _execute_request should
        # be called with the arguments:
        #   method=self.nowplaying
        #   else_cb=self.on_nowplaying_success
        #   arg=self.np
        self.client.state = "idle"
        self.client.np = self.listens[0]
        self.client.tick()
        mocked_execute_request.assert_called_with(
            method=self.client.nowplaying,
            else_cb=self.client.on_nowplaying_success,
            arg=self.client.np,
        )
        # unset self.client.np
        self.client.np = None

        # if self.state is "idle" and self.queue contains listens,
        # _execute_request should be called with the arguments:
        #   method=self.scrobble
        #   else_cb=self.on_scrobble_success
        #   arg=deque(list(self.queue)[:50])
        self.client.state = "idle"
        self.client.add_listens(self.listens)
        self.client.tick()
        mocked_execute_request.assert_called_with(
            method=self.client.scrobble,
            else_cb=self.client.on_scrobble_success,
            arg=deque(list(self.client.queue)[:50]),
        )

    def test_send_nowplaying(self):
        """
        Tests legacy_scrobbler.client.base.ScrobbleClientBase.send_nowplaying()
        """
        self.client.send_nowplaying(self.listens[0])
        self.assertEqual(self.client.np, self.listens[0])

        # unset np
        self.client.np = None

    def test_add_listens(self):
        """
        Tests legacy_scrobbler.client.base.ScrobbleClientBase.add_listens()

        Initializes self.client.queue with items 10 and 0 from self.listens
        (which is in descending chronological order, i.e. most recent first).
        Then, listens 19, 3, 13, and 1 are added to the queue with
        add_listens(). The resulting queue should be [19, 13, 10, 3, 1, 0]
        """
        # initialize queue as [10, 0]
        queue = [self.listens[10], self.listens[0]]
        self.client.queue = deque(queue)

        # add listens [19, 3, 13, 1]
        others = [self.listens[19], self.listens[3], self.listens[13], self.listens[1]]
        self.client.add_listens(others)

        # queue should be [19, 13, 10, 3, 1, 0]
        expected = deque(
            [
                self.listens[19],
                self.listens[13],
                self.listens[10],
                self.listens[3],
                self.listens[1],
                self.listens[0],
            ]
        )

        self.assertEqual(self.client.queue, expected)

    def test_sort_queue(self):
        """
        Tests legacy_scrobbler.client.base.ScrobbleClientBase._sort_queue()

        Initializes self.client.queue with the shuffled self.listens.
        The queue after sorting should be in chronological order.
        self.listens are sorted in descending chronological order (most recent
        first), so after sorting, the queue should be the reverse of
        self.listens
        """
        # set the shuffled self.listens as queue
        queue = self.listens[:]
        random.shuffle(queue)
        self.client.queue = deque(queue)

        # self.listens is reverse chronologically sorted, queue after sort
        # should be reverse of self.listens
        self.client._sort_queue()
        expected = deque(self.listens[::-1])
        self.assertEqual(self.client.queue, expected)

    def test_in_case_of_failure(self):
        """
        Test legacy_scrobbler.client.base.ScrobbleClientBase._in_case_of_failure()

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
        with patch.object(base.Delay, "increase") as mock_method:
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

    def test_callbacks(self):
        # on_handshake
        with patch.object(self.client.delay, "update") as mock_method:
            self.client.on_handshake()
            mock_method.assert_called()

        # on_handshake_success
        self.client.hard_fails = 23
        self.client.state = "no_session"
        with patch.object(self.client.delay, "reset") as mock_method:
            self.client.on_handshake_success()
            mock_method.assert_called()
        self.assertEqual(self.client.hard_fails, 0)
        self.assertEqual(self.client.state, "idle")

        # on_nowplaying_success
        self.client.np = self.listens[0]
        self.client.on_nowplaying_success()
        self.assertIsNone(self.client.np)

        # on_scrobble_success
        self.client.queue = deque(self.listens)
        len_before = len(self.client.queue)
        self.client.on_scrobble_success()
        len_after = len(self.client.queue)
        self.assertEqual(len_before - len_after, 50)
        expected_remaining_queue = deque(self.listens[50:])
        self.assertEqual(self.client.queue, expected_remaining_queue)
