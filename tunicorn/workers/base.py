import random


class Worker(object):
    def handler(self, socket, address):
        pass

    def init_process(self):
        from gevent.server import StreamServer
        self.server = StreamServer(('localhost', 8080 + random.randint(0, 5)), self.handler)
        self.server.serve_forever()
