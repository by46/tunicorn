import errno
import os
import signal

from tunicorn.packages import six
from . import util


def iter_signals():
    """
    return a dictionary
    :return:
    """
    return dict((getattr(signal, name), name[3:].lower())
                for name in dir(signal) if name[:3] == "SIG" and name[3] != "_")


class Signaler(object):
    """

    """
    DEFAULT_SIGNALS = ['HUP', 'QUIT', 'INT', 'TERM', 'TTIN', 'TTOU', 'USR1', 'USR2', 'WINCH']

    def __init__(self, signals=None):
        self.PIPE = []
        self.SIG_QUEUE = []

        if signals is None:
            signals = list(self.DEFAULT_SIGNALS)
        elif isinstance(signals, six.string_types):
            signals = signals.split()
            signals.extend(self.DEFAULT_SIGNALS)

        self.SIGNALS = [getattr(signal, "SIG%s" % x) for x in signals]
        self.SIG_NAMES = iter_signals()

    def init_signals(self):
        if self.PIPE:
            [os.close(fd) for fd in self.PIPE]
        self.PIPE = pair = os.pipe()

        for p in pair:
            util.set_non_blocking(p)
            util.close_on_exec(p)

        [signal.signal(s, self.signal) for s in self.SIGNALS]

    def signal(self, sig, frame):
        if len(self.SIG_QUEUE) < 5:
            self.SIG_QUEUE.append(sig)
            self.wake_up()

    def wake_up(self):
        try:
            os.write(self.PIPE[1], b'.')
        except IOError as e:
            if e.errno not in [errno.EAGAIN, errno.EINTR]:
                raise
