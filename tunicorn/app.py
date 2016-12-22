import logging
import os
import sys
from argparse import ArgumentParser

from tunicorn.arbiter import Arbiter
from tunicorn.config import Config
from tunicorn.workers import choose_worker
from .util import import_app
from .util import parse_address

DEFAULT_CONFIG = {
    'NAME': 'TUNICORN',
    'WORKER_CLASS': 'gevent',
    'WORKERS': 1,
    "BIND": "localhost:8080",
    "ENV": None,
    "UMASK": 0,
    "BACKLOG": 2048,
    "GRACEFUL_TIMEOUT": 5,
    "WORKER_CONNECTIONS": 1000,
    "TIMEOUT": 30,
    "CHDIR": os.getcwd()
}


class Application(object):
    def __init__(self, usage=None, prog=None):
        self.usage = usage
        self.config = None
        self.app_module = None
        self.callable = None
        self.prog = prog or 'Tunicorn'
        self.logger = logging.getLogger('app')
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # add formatter to ch
        ch.setFormatter(formatter)

        # add ch to logger
        self.logger.addHandler(ch)
        self.logger.setLevel(logging.DEBUG)
        self.do_load_config()

    def do_load_config(self):
        parser = ArgumentParser(self.prog, usage=self.usage)
        parser.add_argument('-c', '--config', dest='filename', help='configuration file')
        parser.add_argument('module')

        args = parser.parse_args()

        self.config = Config(os.getcwd(), defaults=DEFAULT_CONFIG)
        self.config.from_pyfile(args.filename)
        self.init_config(args)

    def init_config(self, args):
        # init worker class
        self.app_module = args.module
        worker_class = choose_worker(self.config.WORKER_CLASS)
        if worker_class is None:
            # TODO(benjamin): process customer worker
            pass
        self.config.WORKER_CLASS = worker_class

        self.config.ADDRESS = [parse_address(self.config.BIND)]

        if self.config.UID is None:
            self.config.UID = os.getuid()

        if self.config.GID is None:
            self.config.GID = os.getgid()

    def chdir(self):
        os.chdir(self.config.CHDIR)
        sys.path.insert(0, self.config.CHDIR)

    def load(self):
        self.chdir()
        return import_app(self.app_module)

    @property
    def handler(self):
        if self.callable is None:
            self.callable = self.load()
        return self.callable

    def run(self):
        self.load()
        try:
            Arbiter(self).run()
        except RuntimeError as e:
            self.logger.exception(e)
            sys.exit(1)


def run():
    Application('%(prog)s [OPTIONS] [APP_MODULE]').run()
