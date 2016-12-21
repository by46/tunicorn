import os
import sys
from argparse import ArgumentParser

from tunicorn.arbiter import Arbiter
from tunicorn.config import Config
from tunicorn.workers import choose_worker

DEFAULT_CONFIG = {
    'NAME': 'TUNICORN',
    'WORKER_CLASS': 'gevent',
    'WORKERS': 1
}


class Application(object):
    def __init__(self, usage=None, prog=None):
        self.usage = usage
        self.config = None
        self.prog = prog or 'Tunicorn'
        self.logger = None
        self.do_load_config()

    def do_load_config(self):
        parser = ArgumentParser(self.prog, usage=self.usage)
        parser.add_argument('-c', '--config', dest='filename', help='configuration file')
        parser.add_argument('module')

        args = parser.parse_args()

        self.config = Config(os.getcwd(), defaults=DEFAULT_CONFIG)
        self.config.from_pyfile(args.filename)
        self.init_config()

    def init_config(self):
        # init worker class
        worker_class = choose_worker(self.config.WORKER_CLASS)
        if worker_class is None:
            # TODO(benjamin): process customer worker
            pass
        self.config.WORKER_CLASS = worker_class

    def run(self):
        try:
            Arbiter(self).run()
        except RuntimeError as e:
            self.logger.exception(e)
            sys.exit(1)
