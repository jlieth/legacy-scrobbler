import datetime

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
        is_tz_aware = isinstance(self.date.tzinfo, datetime.tzinfo)
        if not is_tz_aware:
            raise DateWithoutTimezoneError()

    @property
    def timestamp(self):
        return int(self.date.timestamp())

    def nowplaying_params(self):
        return {
            "a": self.artist_name,
            "t": self.track_title,
            "b": self.album_title or "",
            "l": self.length or "",
            "n": self.tracknumber or "",
            "m": self.mb_trackid or "",
        }

    def submit_params(self, idx=0):
        return {
            f"a[{idx}]": self.artist_name,
            f"t[{idx}]": self.track_title,
            f"i[{idx}]": self.timestamp,
            f"o[{idx}]": self.source,
            f"r[{idx}]": self.rating or "",
            f"l[{idx}]": self.length or "",
            f"b[{idx}]": self.album_title or "",
            f"n[{idx}]": self.tracknumber or "",
            f"m[{idx}]": self.mb_trackid or "",
        }
