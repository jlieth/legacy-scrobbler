import datetime
from typing import Optional

from legacy_scrobbler.exceptions import DateWithoutTimezoneError


class Listen:
    def __init__(
        self,
        date: datetime.datetime,
        artist_name: str,
        track_title: str,
        album_title: str = None,
        length: int = None,
        tracknumber: int = None,
        mb_trackid: str = None,
        source: str = "P",
        rating: str = None,
    ):
        """
        Creates a Listen instance.
        date must be timezone-aware.

        How to use:
        >>> import datetime
        >>> from legacy_scrobbler import Listen
        >>> d = datetime.datetime.now(datetime.timezone.utc)
        >>> l = Listen(d, "Artist", "Track", length=200)
        """
        self.date = date
        self.artist_name = artist_name
        self.track_title = track_title
        self.album_title = album_title
        self.length = length
        self.tracknumber = tracknumber
        self.mb_trackid = mb_trackid
        self.source = source
        self.rating = rating

        self.validate_date()

    def validate_date(self):
        """
        Checks whether self.date is timezone-aware.

        :raises legacy_scrobbler.exceptions.DateWithoutTimezoneError:
            If self.date is not timezone-aware.
        """
        is_tz_aware = isinstance(self.date.tzinfo, datetime.tzinfo)
        if not is_tz_aware:
            raise DateWithoutTimezoneError()

    @property
    def timestamp(self) -> int:
        return int(self.date.timestamp())

    @property
    def required_play_time(self) -> int:
        """
        Calculates the length in seconds this listen needs to be played to
        count as a scrobble according to the Audioscrobbler protocol.

        The Audioscrobbler protocol defines two rules about whether or not
        a listen should be submitted. The rules are:
        1) The track needs to be at least 30 seconds long.
        2) The playtime of the track has to be long enough. "Long enough" means
           2.1) Half the song's length if it is shorter than eight minutes
           2.2) 240 seconds otherwise

        This method calculates 2).

        >>> import datetime
        >>> now = datetime.datetime.now(datetime.timezone.utc)
        >>> l1 = Listen(now, "Artist", "Track", length=111)
        >>> l1.required_play_time
        56
        >>> l2 = Listen(now, "Artist", "Track", length=500)
        >>> l2.required_play_time
        240

        :return: int. Length in seconds of playtime required for scrobbling
        """
        if self.length > 480:
            return 240
        else:
            return round(self.length / 2)

    def nowplaying_params(self):
        return {
            "a": self.artist_name,
            "t": self.track_title,
            "b": self.album_title or "",
            "l": self.length or "",
            "n": self.tracknumber or "",
            "m": self.mb_trackid or "",
        }

    def scrobble_params(self, idx=0):
        return {
            f"a[{idx}]": self.artist_name,
            f"t[{idx}]": self.track_title,
            f"i[{idx}]": self.timestamp,
            f"o[{idx}]": self.source,
            f"r[{idx}]": self.rating or "",
            f"l[{idx}]": self.length or 0,
            f"b[{idx}]": self.album_title or "",
            f"n[{idx}]": self.tracknumber or "",
            f"m[{idx}]": self.mb_trackid or "",
        }

    def eligible_for_scrobbling(
        self, reference: Optional[datetime.datetime] = None
    ) -> bool:
        """
        Determines whether the Listen object should be scrobbled.
        The reference datetime must be timezone-aware.

        The Audioscrobbler protocol defines two rules about whether or not
        a listen should be submitted. The rules are:
        1) The track needs to be at least 30 seconds long.
        2) The playtime of the track has to be long enough. "Long enough" means
           2.1) Half the song's length if it is shorter than eight minutes
           2.2) 240 seconds otherwise

        However, a Listen object contains absolutely no context to determine
        its playtime. It only contains the start time in its date attribute.
        This is why a reference datetime is necessary.

        The reference datetime has to be chronologically later than the start
        time of the listen. The time span between the start time and the
        reference datetime defines the time in which the track could be played.
        If this time span is long enough to allow for the required playtime to
        pass, the listen is eligible for scrobbling.

        Finding a useful reference datetime depends on the source of the listen.

        In streaming data sources (e.g. a D-BUS listener that receives playing
        information live from a media player), you will usually know when a
        track starts playing. At this point you can already initialize a Listen
        object with the start time. You will probably want to use the current
        datetime (with timezone) as reference when checking a live listen.

        In non-streaming data sources (e.g. scrobble logs like Last.fm dumps),
        you probably process multiple listens at once. Assuming the listens
        are sorted chronologically by timestamp, the reference datetime for
        a listen i should probably be the date of the listen i+1.

        Consider this log of listens:

        [2019-02-26 11:26:38.864000+00:00] Listen1: Artist1 - Track1 (3:30)
        [2019-02-26 11:26:38.871000+00:00] Listen2: Artist2 - Track2 (4:00)
        [2019-02-26 11:31:07.595000+00:00] Listen3: Artist3 - Track3 (4:28)

        The reference datetime for Listen1 is the datetime of Listen2.
        The reference datetime for Listen2 is the datetime of Listen3.
        The reference datetime for Listen3 is None (since you can't guess at
        the edge of a list).

        >>> import datetime
        >>> import dateutil.parser
        >>> from legacy_scrobbler import Listen
        >>> d1 = dateutil.parser.parse("2019-02-26 11:26:38.864000+00:00")
        >>> d2 = dateutil.parser.parse("2019-02-26 11:26:38.871000+00:00")
        >>> d3 = dateutil.parser.parse("2019-02-26 11:31:07.595000+00:00")
        >>> l1 = Listen(d1, "Artist1", "Track1", length=210)
        >>> l2 = Listen(d2, "Artist2", "Track2", length=240)
        >>> l3 = Listen(d3, "Artist3", "Track3", length=268)
        >>> l1.eligible_for_scrobbling(reference=l2.date)
        False
        >>> l2.eligible_for_scrobbling(reference=l3.date)
        True
        >>> l3.eligible_for_scrobbling(reference=None)
        True

        :param reference: datetime.datetime object. Reference date (see help)
        :return: bool. Whether the listen should be scrobbled.
        """
        # if length is < 30 seconds, the track is not eligible either way
        if self.length < 30:
            return False

        # if no reference date was given, assume enough play time
        if reference is None:
            return True

        # determine if enough time is between the listen date and the
        # reference date to allow for the required play time
        time_between = reference - self.date
        return time_between.seconds >= self.required_play_time
