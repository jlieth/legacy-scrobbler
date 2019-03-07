import logging

import coloredlogs

from legacy_scrobbler.listen import Listen  # noqa: F401
from legacy_scrobbler.network import Network  # noqa: F401
from legacy_scrobbler.version import __version__, __version_info__  # noqa: F401
from legacy_scrobbler.clients.legacy import LegacyScrobbler  # noqa: F401


# set up logging
logger = logging.getLogger("legacy_scrobbler")
coloredlogs.install(level="DEBUG", logger=logger)
