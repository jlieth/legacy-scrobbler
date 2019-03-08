import datetime


class Delay:
    def __init__(self, options: dict = None):
        self._seconds = 0
        self._start_time = None
        self._options = {"base": 30, "max": 300, "multiplier": 2}

        if options:
            self._options.update(options)

    def start(self):
        """Sets self._start_time to now and increases delay."""
        self.reset()
        self.update()
        self.increase()

    def update(self):
        """Sets self._start_time to now."""
        self._start_time = datetime.datetime.now(datetime.timezone.utc)

    def reset(self):
        """Resets both self._start_time and self._seconds."""
        self._seconds = 0
        self._start_time = None

    @property
    def is_active(self) -> bool:
        """Determines whether a delay is currently in effect."""
        if self.remaining.seconds > 0:
            return True
        else:
            return False

    @property
    def remaining(self) -> datetime.timedelta:
        """
        Calculates the remaining timedelta until the delay is over.

        Will return a timedelta of zero if self._seconds is zero or
        self._start_time is None.

        :return: datetime.timedelta until the delay is over
        """
        # timedelta is zero of no delay is set_delay_start_time
        if self._seconds == 0:
            return datetime.timedelta(seconds=0)

        # timedelta is zero if self._start_time isn't set
        if self._start_time is None:
            return datetime.timedelta(seconds=0)

        # calculate end of delay
        delay_delta = datetime.timedelta(seconds=self._seconds)
        delay_end = self._start_time + delay_delta

        # if end of delay is in the past, return a timedelta of zero
        # else return the time difference between now and end of delay
        now = datetime.datetime.now(datetime.timezone.utc)
        if delay_end <= now:
            return datetime.timedelta(seconds=0)
        else:
            return delay_end - now

    def increase(self):
        """Increases the delay based on self.delay_options."""
        base_delay = self._options["base"]
        max_delay = self._options["max"]
        multiplier = self._options["multiplier"]
        self._seconds = (self._seconds * multiplier) or base_delay

        if self._seconds > max_delay:
            self._seconds = max_delay
