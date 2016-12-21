import signal

from tunicorn.signaler import Signaler


class Worker(Signaler):
    def __init__(self, age, parent_pid, sockets, app, timeout, logger=None):
        super(Worker, self).__init__()
        self.age = age
        self.parent_id = parent_pid
        self.sockets = sockets
        self.app = app
        self.timeout = timeout
        self.booted = False

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
        handler = getattr(self, 'handler_%s' % sig_name, None)
        if not handler:
            self.logger.error('Unhandled signal: %s', sig_name)
            return

        self.logger.info('Handling signal: %s', sig_name)
        handler()

    def handler(self, socket, address):
        pass

    def init_process(self):
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
