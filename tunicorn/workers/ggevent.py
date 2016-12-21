import random

from .base import Worker


class GeventWorker(Worker):
    def run(self):
        from gevent.server import StreamServer
        self.server = StreamServer(('localhost', 8080 + random.randint(0, 5)), self.handler)
        self.server.serve_forever()
