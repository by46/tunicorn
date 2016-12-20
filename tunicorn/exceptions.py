class BaseError(Exception):
    """

    """


class TunicornException(BaseError):
    """

    """


class HaltServerException(TunicornException):
    """

    """

    def __init__(self, reason, exit_status=1):
        self.reason = reason
        self.exit_status = exit_status
        msg = "HaltServer Exception %r %d" % (self.reason, self.exit_status)
        super(HaltServerException, self).__init__(msg)

