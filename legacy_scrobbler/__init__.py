import logging

from legacy_scrobbler.client import ScrobblerClient  # noqa: F401
from legacy_scrobbler.listen import Listen  # noqa: F401
from legacy_scrobbler.network import Network  # noqa: F401
from legacy_scrobbler.version import __version__, __version_info__  # noqa: F401


# set up logging
logger = logging.getLogger("legacy_scrobbler")
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s %(name)-12s %(levelname)-8s %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)
