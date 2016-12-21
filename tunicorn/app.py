import os
import sys
from argparse import ArgumentParser

from tunicorn.arbiter import Arbiter
from tunicorn.config import Config

DEFAULT_CONFIG = {
    'NAME': 'TUNICORN'
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

    def run(self):
        try:
            Arbiter(self).run()
        except RuntimeError as e:
            self.logger.exception(e)
            sys.exit(1)
