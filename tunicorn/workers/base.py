import os
import signal
import sys
import time

from tunicorn.signaler import Signaler
from tunicorn.util import seed
from tunicorn.util import set_owner_process
from .workertmp import WorkerTmp


class Worker(Signaler):
    def __init__(self, age, parent_pid, sockets, app, timeout, logger=None):
        super(Worker, self).__init__()
        self.logger = logger or app.logger
        self.age = age
        self.parent_id = parent_pid
        self.sockets = sockets
        self.app = app
        self.config = self.app.config
        self.timeout = timeout
        self.booted = False
        self.alive = True
        self.tmp = WorkerTmp(self.config)
        self.worker_connections = self.config.WORKER_CONNECTIONS

    # --------------------------------------------------
    # signals handlers
    # --------------------------------------------------
    def handle_exit(self):
        self.alive = False

    def handle_quit(self):
        self.alive = False
        time.sleep(0.1)
        sys.exit(0)

    def handle_abort(self):
        self.alive = False
        sys.exit(1)

    # --------------------------------------------------
    # override methods
    # --------------------------------------------------
    def init_signals(self):
        super(Worker, self).init_signals()

        # Don't let SIGTERM and SIGUSR1 disturb active requests
        # by interrupting system calls
        if hasattr(signal, 'siginterrupt'):  # python >= 2.6
            signal.siginterrupt(signal.SIGTERM, False)
            signal.siginterrupt(signal.SIGUSR1, False)

        if hasattr(signal, 'set_wakeup_fd'):
            signal.set_wakeup_fd(self.PIPE[1])

    def signal(self, sig, frame):
        sig_name = self.SIG_NAMES.get(sig)
        handler = getattr(self, 'handle_%s' % sig_name, None)
        if not handler:
            self.logger.error('Unhandled signal: %s', sig_name)
            return

        self.logger.info('Handling signal: %s', sig_name)
        handler()

    def handler(self, socket, address):
        pass

    def init_process(self):

        # set environment
        if self.config.ENV:
            for k, v in self.config.ENV.items():
                os.environ[k] = v
        set_owner_process(self.config.UID, self.config.GID, initgroups=self.config.INITGROUPS)

        seed()

        self.init_signals()

        self.booted = True
        self.run()

    def run(self):
        """\
        This is the mainloop of a worker process. You should override
        this method in a subclass to provide the intended behaviour
        for your particular evil schemes.
        """
        raise NotImplementedError()

    # --------------------------------------------------
    # properties methods
    # --------------------------------------------------
    @property
    def pid(self):
        return os.getpid()

    # --------------------------------------------------
    # public methods
    # --------------------------------------------------
    def __str__(self):
        return '<Worker {0}>'.format(self.pid)

    def notify(self):
        """\
        Your worker subclass must arrange to have this method called
        once every ``self.timeout`` seconds. If you fail in accomplishing
        this task, the master process will murder your workers.
        """
        self.tmp.notify()
