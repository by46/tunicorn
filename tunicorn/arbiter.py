import errno
import logging
import os
import random
import select
import signal
import sys
import time

import fcntl

from tunicorn.workers import Worker


class ArbiterBase(object):
    def __init__(self):
        self.PIPE = []
        self.SIG_QUEUE = []
        self.WORKERS = {}
        self.SIGNALS = [getattr(signal, "SIG%s" % x)
                        for x in "HUP QUIT INT TERM TTIN TTOU USR1 USR2 WINCH".split()]
        self.SIG_NAMES = dict(
            (getattr(signal, name), name[3:].lower()) for name in dir(signal)
            if name[:3] == "SIG" and name[3] != "_"
        )

    def init_signals(self):
        if self.PIPE:
            [os.close(fd) for fd in self.PIPE]
        self.PIPE = pair = os.pipe()

        for p in pair:
            set_non_blocking(p)
            close_on_exec(p)

        [signal.signal(s, self.signal) for s in self.SIGNALS]

    def signal(self, sig, frame):
        print sig, frame
        if len(self.SIG_QUEUE) < 5:
            self.SIG_QUEUE.append(sig)
            self.wakeup()

    def start(self):
        self.init_signals()

    def run(self):
        self.start()

    def wakeup(self):
        try:
            os.write(self.PIPE[1], b'.')
        except IOError as e:
            if e.errno not in [errno.EAGAIN, errno.EINTR]:
                raise

    def sleep(self):
        try:
            ready = select.select([self.PIPE[0]], [], [], 5.0)
            if not ready[0]:
                return
            while os.read(self.PIPE[0], 1):
                pass
        except select.error as e:
            if e.args[0] not in [errno.EAGAIN, errno.EINTR]:
                raise
        except OSError as e:
            if e.errno not in [errno.EAGAIN, errno.EINTR]:
                raise
        except KeyboardInterrupt:
            sys.exit()


class Arbiter(ArbiterBase):
    def __init__(self):
        self.num_workers = 2
        self.logger = logging.getLogger('arbiter')
        self.logger.
        super(Arbiter, self).__init__()

    @staticmethod
    def handle_hup():
        print 'process hup signal'

    def run(self):
        super(Arbiter, self).run()
        while True:
            self.manage_workers()
            print 'sleep 1 seconds'
            sig = self.SIG_QUEUE.pop(0) if len(self.SIG_QUEUE) else None
            if sig is None:
                self.sleep()
                print 'sig in'

            if sig not in self.SIG_NAMES:
                self.logger.info('Ignoring unknown signal: %s', sig)
                continue

            sig_name = self.SIG_NAMES.get(sig)
            handler = getattr(self, 'handler_%s' % sig_name, None)
            if not handler:
                self.logger.error('Unhandled signal: %s', sig_name)
                continue

            self.logger.info('Handling signal: %s', sig_name)
            handler()
            self.wakeup()

    def manage_workers(self):
        if len(self.WORKERS.keys()) < self.num_workers:
            self.spawn_workers()

    def spawn_workers(self):
        for i in range(self.num_workers - len(self.WORKERS.keys())):
            self.spawn_worker()
            time.sleep(0.1 * random.random())
        pass

    def spawn_worker(self):
        worker = Worker()
        pid = os.fork()
        if pid != 0:
            self.WORKERS[pid] = worker
            return

        worker_pid = os.getpid()
        try:
            print 'worker ', worker_pid
            worker.init_process()
        except Exception as e:
            print e
            sys.exit()


def set_non_blocking(fd):
    flags = fcntl.fcntl(fd, fcntl.F_GETFL) | os.O_NONBLOCK
    fcntl.fcntl(fd, fcntl.F_SETFL, flags)


def close_on_exec(fd):
    flags = fcntl.fcntl(fd, fcntl.F_GETFD)
    flags |= fcntl.FD_CLOEXEC
    fcntl.fcntl(fd, fcntl.F_SETFD, flags)
