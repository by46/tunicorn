from .base import Worker
from .ggevent import GeventWorker


def choose_worker(worker_class):
    if worker_class == 'gevent':
        return GeventWorker
    else:
        return None
