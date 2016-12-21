import os.path
import sys

__author__ = "benjamin.c.yan@newegg.com"
__version__ = "0.0.1"
SERVER_SOFTWARE = "tunicorn/{0}".format(__version__)

sys.path.insert(0, os.path.normpath(os.path.join(__file__, '..', 'packages')))
