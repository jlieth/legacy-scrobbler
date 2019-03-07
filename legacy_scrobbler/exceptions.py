class LegacyScrobblerFatalException(Exception):
    """
    Superclass for Exceptions that can't realistically be recovered from
    during runtime.
    """


class LegacyScrobblerNonFatalException(Exception):
    """
    Superclass for Exceptions that clients may want to handle (e.g. auth
    errors by re-initiating the handshake)
    """


class HardFailureError(LegacyScrobblerNonFatalException):
    """
    Exception that is raised in situations where the Audioscrobbler protocol
    calls for incrementing a hard failure count. This Exception is considered
    non-fatal and is meant to be caught by the calling code in order to
    increment a failure and delay counter.
    """

    pass


class RequestsError(LegacyScrobblerNonFatalException):
    """
    Exception that is raised whenever a requests.exceptions.RequestException
    from the underlying requests library is caught. For now this exception is
    considered non-fatal and should be treated as a hard failure.
    """

    pass


class HandshakeError(LegacyScrobblerFatalException):
    """
    Superclass for fatal exceptions that can be raised during a handshake
    when either the client, credentials or system is configured in a way
    that will never lead to a successful handshake.
    """

    pass


class ClientBannedException(HandshakeError):
    """
    Exception that is raised by Network.handshake() if the response from the
    server is "BANNED". This means that the client identified by its id and
    version combination is considered to be disruptive and/or in violation
    of the scrobbler protocol.

    This is a fatal exception that can't be corrected during runtime.
    """

    def __init__(self):
        msg = "The scrobbler client is banned from this network."
        super().__init__(msg)


class BadAuthException(HandshakeError):
    """
    Exception that is raised by Network.handshake() if the response from the
    server is "BADAUTH". This means that the password hash provided by the
    user is wrong for the given username.

    This is a fatal exception that can't be corrected during runtime.
    """

    def __init__(self):
        msg = "Authentication failed. Check credentials and try again."
        super().__init__(msg)


class BadTimeException(HandshakeError):
    """
    Exception that is raised by Network.handshake() if the response from the
    server is "BADTIME". This means that the timestamp sent to the server
    in the handshake request is too far off from the correct timestamp.

    This is a fatal exception that can't be corrected during runtime.
    """

    def __init__(self):
        msg = "Reported timestamp is off. Check your system clock."
        super().__init__(msg)


class BadSessionError(LegacyScrobblerNonFatalException):
    """
    Exception that is raised by Network.scrobble() and Network.nowplaying()
    if no session exists or if the response from the server after either
    request is "BADSESSION". This is a non-fatal exception and can be
    handled by the calling code by falling back to the handshake phase.
    """


class UsageException(LegacyScrobblerFatalException):
    """
    Superclass for exceptions that are raised when the legacy_scrobbler is
    used in an unintended way. These exceptions are considered fatal.
    """

    pass


class DateWithoutTimezoneError(UsageException):
    """
    Raised by the `Listen` constructor when a timezone-naive datetime object
    was handed over during instantiation. The exception inherits from
    UsageException which inherits from LegacyScrobblerFatalException. Thus,
    trying to create a Listen object with a timezone-naive date is considered
    fatal.
    """

    def __init__(self):
        msg = "Listen constructor received a date without timezone info."
        super().__init__(msg)


class SubmissionWithoutListensError(UsageException):
    """
    Raised by Network.scrobble() if called without listens objects as arguments.
    This exception is considered fatal. While calling scrobble without arguments
    wouldn't in itself lead to any internal error in the LegacyScrobbler or
    Network, it's probably a sign that the calling code contains an error.
    """

    def __init__(self):
        msg = "Network.scrobble() has been called without any listens to scrobble."
        super().__init__(msg)
