import time
from functools import partial

_socket = __import__('socket')

try:
    import gevent
except ImportError:
    raise RuntimeError("You need gevent installed to use this worker.")
from gevent.pool import Pool
from gevent.server import StreamServer
from gevent.socket import socket
from .base import Worker
import six


class GeventWorker(Worker):
    def patch(self):
        from gevent import monkey
        monkey.noisy = False

        monkey.patch_all(subprocess=True)

        # patch sockets
        sockets = []
        for s in self.sockets:
            if six.PY3:
                sockets.append(socket(s.FAMILY, _socket.SOCK_STREAM,
                                      fileno=s.sock.fileno()))
            else:
                sockets.append(socket(s.FAMILY, _socket.SOCK_STREAM,
                                      _sock=s))
        self.sockets = sockets

    def handle(self, listener, client, addr):
        pass

    def run(self):
        servers = []
        ssl_args = {}

        for s in self.sockets:
            s.setblocking(1)
            pool = Pool(self.worker_connections)

            hfun = partial(self.handle, s)
            server = StreamServer(s, handle=hfun, spawn=pool, **ssl_args)

            server.start()
            servers.append(server)

        while self.alive:
            self.notify()
            gevent.sleep(1.0)

        try:
            # Stop accepting requests
            for server in servers:
                if hasattr(server, 'close'):  # gevent 1.0
                    server.close()
                if hasattr(server, 'kill'):  # gevent < 1.0
                    server.kill()

            # Handle current requests until graceful_timeout
            ts = time.time()
            while time.time() - ts <= self.config.GRACEFUL_TIMEOUT:
                accepting = 0
                for server in servers:
                    if server.pool.free_count() != server.pool.size:
                        accepting += 1

                # if no server is accepting a connection, we can exit
                if not accepting:
                    return

                self.notify()
                gevent.sleep(1.0)

            # Force kill all active the handlers
            self.log.warning("Worker graceful timeout (pid:%s)" % self.pid)
            [server.stop(timeout=1) for server in servers]
        except:
            pass

    def init_process(self):
        # monkey patch here
        self.patch()

        # reinit the hub
        from gevent import hub
        hub.reinit()

        # then initialize the process
        super(GeventWorker, self).init_process()
