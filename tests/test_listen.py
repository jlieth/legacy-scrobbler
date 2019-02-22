import datetime
import unittest

from legacy_scrobbler import Listen
from legacy_scrobbler.exceptions import DateWithoutTimezoneError


class ListenTests(unittest.TestCase):
    def setUp(self):
        self.date = datetime.datetime.now(datetime.timezone.utc)
        self.timestamp = int(self.date.timestamp())
        self.listen = Listen(date=self.date, artist_name="Artist", track_title="Track")
        self.listen_with_all_info = Listen(
            date=self.date,
            artist_name="Artist",
            track_title="Track",
            album_title="Album",
            length=100,
            tracknumber=1,
            mb_trackid="foobar",
            source="P",
            rating="L",
        )

    def test_timestamp(self):
        self.assertEqual(self.listen.timestamp, self.timestamp)

    def test_tz_naive_date_raises_exception(self):
        naive_date = datetime.datetime.now()
        with self.assertRaises(DateWithoutTimezoneError):
            Listen(date=naive_date, artist_name="Artist", track_title="Title")

    def test_nowplaying_params(self):
        self.assertEqual(
            self.listen.nowplaying_params(),
            {"a": "Artist", "t": "Track", "b": "", "l": "", "n": "", "m": ""},
        )

        self.assertEqual(
            self.listen_with_all_info.nowplaying_params(),
            {
                "a": "Artist",
                "t": "Track",
                "b": "Album",
                "l": 100,
                "n": 1,
                "m": "foobar",
            },
        )

    def test_submit_params(self):
        self.assertEqual(
            self.listen.scrobble_params(),
            {
                "a[0]": "Artist",
                "t[0]": "Track",
                "i[0]": self.timestamp,
                "o[0]": "P",
                "r[0]": "",
                "l[0]": 0,
                "b[0]": "",
                "n[0]": "",
                "m[0]": "",
            },
        )

        self.assertEqual(
            self.listen_with_all_info.scrobble_params(idx=10),
            {
                "a[10]": "Artist",
                "t[10]": "Track",
                "i[10]": self.timestamp,
                "o[10]": "P",
                "r[10]": "L",
                "l[10]": 100,
                "b[10]": "Album",
                "n[10]": 1,
                "m[10]": "foobar",
            },
        )
