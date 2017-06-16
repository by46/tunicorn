import errno
import os
import random
import select
import signal
import sys
import time
import traceback

from tunicorn import __version__
from .exceptions import AppImportException
from .exceptions import HaltServerException
from .signaler import Signaler
from .sock import create_sockets


class Arbiter(Signaler):
    # A flag indicating if a worker failed to
    # to boot. If a worker process exist with
    # this error code, the arbiter will terminate.
    WORKER_BOOT_ERROR = 3

    # A flag indicating if an application failed to be loaded
    APP_LOAD_ERROR = 4

    def __init__(self, app, signals=None):
        super(Arbiter, self).__init__(signals="CHLD")
        self._last_active_count = None
        self.app = app
        self.worker_class = self.app.config.WORKER_CLASS
        self.num_workers = self.app.config.WORKERS
        # TODO(benjamin): process logger
        self.timeout = self.app.config.TIMEOUT
        self.logger = self.app.logger

        self.master_name = "Master"
        # TODO(benjamin): set from configuration
        self.proc_name = 'Demo'

        self.pidfile = None
        self.worker_age = 0
        self.master_pid = 0
        self.reexec_pid = 0
        self.pid = None

        self.WORKERS = {}
        self.LISTENERS = []

    def handle_cld(self):
        self.reap_workers()
        self.wake_up()

    def handle_hup(self):
        self.logger.info("Hang up: %s", self.master_name)
        self.reload()

    @staticmethod
    def handle_term():
        """SIGTERM handling

        :return:
        """
        raise StopIteration

    def handle_int(self):
        """SIGINT handling

        :return:
        """
        self.stop(False)
        raise StopIteration

    def handle_quit(self):
        self.stop(False)
        raise StopIteration

    def handle_ttin(self):
        """SIGTTIN handling
        Increase the number of workers by one
        :return:
        """
        self.num_workers += 1
        self.manage_workers()

    def handle_ttou(self):
        """SIGTTOU handling

        :return:
        """
        if self.num_workers <= 1:
            return

        self.num_workers -= 1
        self.logger.debug('ttou %s', self.num_workers)
        self.manage_workers()

    def handle_usr1(self):
        """SIGUSR1 handling
        Kill all workers by sending them a SIGUSR1

        """
        # TODO(benjamin): reopen logger
        self.kill_workers(signal.SIGUSR1)

    def handle_usr2(self):
        """SIGUSR2 handling
        Create a new master/worker set as a slave of the current
        master without affecting old workers. Use this to do live
        deployment with the ability to backout a change.

        """
        self.reexec()

    def handle_winch(self):
        """SIGWINCH handling

        :return:
        """
        # TODO(benjamin): daemon process

    # --------------------------------------------------
    # workers methods
    # --------------------------------------------------
    def manage_workers(self):
        if len(self.WORKERS.keys()) < self.num_workers:
            self.spawn_workers()

        workers = self.WORKERS.items()
        workers = sorted(workers, key=lambda w: w[1].age)
        while len(workers) > self.num_workers:
            pid, _ = workers.pop(0)
            self.kill_worker(pid, signal.SIGTERM)

        active_worker_count = len(workers)
        if self._last_active_count != active_worker_count:
            self._last_active_count = active_worker_count
            self.logger.debug('{0} workers'.format(active_worker_count),
                              extra={"metric": "gunicorn.workers",
                                     "value": active_worker_count,
                                     "mtype": "gauge"})

    def spawn_workers(self):
        for i in range(self.num_workers - len(self.WORKERS.keys())):
            self.spawn_worker()
            time.sleep(0.1 * random.random())

    def spawn_worker(self):
        self.worker_age += 1

        worker = self.worker_class(self.worker_age, self.pid, self.LISTENERS,
                                   self.app,
                                   self.timeout / 2.0)
        pid = os.fork()
        if pid != 0:
            # Parent process
            self.WORKERS[pid] = worker
            return

        worker_pid = os.getpid()
        try:
            self.logger.info("Booting worker with pid: %s", worker_pid)
            worker.init_process()
            sys.exit(0)
        except AppImportException as e:
            self.logger.debug('Exception while loading the application', exc_info=True)
            sys.exit(self.APP_LOAD_ERROR)
        except Exception as e:
            self.logger.exception('Exception in worker process')
            if not worker.booted:
                sys.exit(self.WORKER_BOOT_ERROR)
            sys.exit(-1)
        finally:
            self.logger.info('Worker exiting (pid: %s)', worker_pid)
            try:
                worker.tmp.close()
            except:
                self.logger.warning('Exception during worker exit: \n %s',
                                    traceback.format_exc())

    def kill_workers(self, sig):
        workers = list(self.WORKERS.keys())
        for pid in workers:
            self.kill_worker(pid, sig)

    def kill_worker(self, pid, sig):
        try:
            os.kill(pid, sig)
        except OSError as e:
            if e.errno == errno.ESRCH:
                try:
                    worker = self.WORKERS.pop(pid)
                    worker.tmp.close()
                except(OSError, KeyError):
                    return
            raise

    def reap_workers(self):
        """
        reap workers to avoid zombie process
        :return:
        """
        try:
            while True:
                # os.WNOHANG control waitpid nonblock when any process exit status available
                # then wpid is 0
                wpid, status = os.waitpid(-1, os.WNOHANG)
                if not wpid:
                    break
                if self.reexec_pid == wpid:
                    self.reexec_pid = 0
                else:
                    exit_code = status >> 8
                    if exit_code == self.WORKER_BOOT_ERROR:
                        reason = "Worker failed to boot."
                        raise HaltServerException(reason, exit_code)
                    if exit_code == self.APP_LOAD_ERROR:
                        reason = "App failed to load."
                        raise HaltServerException(reason, exit_code)

                    worker = self.WORKERS.pop(wpid, None)
                    if not worker:
                        continue

                    # TODO(benjamin): shut down worker
                    worker.tmp.close()
        except OSError as e:
            # raise OSError when  master have no child process
            if e.errno != errno.ECHILD:
                raise

    def murder_workers(self):
        if not self.timeout:
            return

        for pid, worker in self.WORKERS.items():
            try:
                if time.time() - worker.tmp.last_update() <= self.timeout:
                    continue
            except (OSError, IOError):
                continue

            if not worker.aborted:
                self.logger.critical("WORKER TIMEOUT (pid:%s)", pid)
                worker.aborted = True
                self.kill_worker(pid, signal.SIGABRT)
            else:
                self.kill_worker(pid, signal.SIGKILL)

    # --------------------------------------------------
    # management methods
    # --------------------------------------------------
    def sleep(self):
        try:
            ready = select.select([self.PIPE[0]], [], [], 5.0)
            if not ready[0]:
                return
            while os.read(self.PIPE[0], 1):
                pass
        except select.error as e:
            if e.args[0] not in [errno.EAGAIN, errno.EINTR]:
                raise
        except OSError as e:
            if e.errno not in [errno.EAGAIN, errno.EINTR]:
                raise
        except KeyboardInterrupt:
            sys.exit()

    def halt(self, reason=None, exit_status=0):
        self.stop()
        self.logger.info('Shutting down:%s', self.master_name)

        if reason is not None:
            self.logger.info("Reason is %s", reason)

        if self.pidfile is not None:
            self.pidfile.unlink()

        sys.exit(exit_status)

    def start(self):
        """Initialize the arbiter
        Start listening and set pidfile if needed.
        :return:
        """
        self.logger.info('Starting tunicorn %s', __version__)

        if 'TUNICORN_PID' in os.environ:
            self.master_pid = int(os.environ.get('TUNICORN_PID'))
            self.proc_name += '.2'

        self.pid = os.getpid()
        # TODO(benjamin): process pidfile

        self.init_signals()

        # TODO(benjamin): process socket listener
        if not self.LISTENERS:
            self.LISTENERS = create_sockets(self.app.config, self.logger)

        listeners_str = ",".join([str(l) for l in self.LISTENERS])
        self.logger.debug("Arbiter booted")
        self.logger.info("Listening at: %s (%s)", listeners_str, self.pid)
        self.logger.info("Using worker: %s", self.worker_class.__name__)

    def stop(self, graceful=True):
        if self.reexec_pid == 0 and self.master_pid == 0:
            for l in self.LISTENERS:
                l.close()
        self.LISTENERS = []

        sig = signal.SIGTERM
        if not graceful:
            sig = signal.SIGQUIT

        # TODO(benjamin): graceful timeout come from configuration
        limit = time.time() + 5

        self.kill_workers(sig)

        while self.WORKERS and time.time() < limit:
            time.sleep(0.1)

        self.kill_workers(signal.SIGKILL)

    # TODO(benjamin): reload code and configuration
    def reload(self):
        pass

    def reexec(self):
        pass

    # --------------------------------------------------
    # public methods
    # --------------------------------------------------
    def run(self):
        self.start()
        try:
            self.manage_workers()

            while True:
                sig = self.SIG_QUEUE.pop(0) if len(self.SIG_QUEUE) else None
                if sig is None:
                    self.sleep()
                    self.murder_workers()
                    self.manage_workers()
                    continue

                if sig not in self.SIG_NAMES:
                    self.logger.info('Ignoring unknown signal: %s', sig)
                    continue

                sig_name = self.SIG_NAMES.get(sig)
                handler = getattr(self, 'handle_%s' % sig_name, None)
                if not handler:
                    self.logger.error('Unhandled signal: %s', sig_name)
                    continue

                self.logger.info('Handling signal: %s', sig_name)
                handler()
                self.wake_up()
        except StopIteration:
            self.halt()
        except KeyboardInterrupt:
            self.halt()
        except HaltServerException as e:
            self.halt(reason=e.reason, exit_status=e.exit_status)
        except SystemExit:
            raise
        except Exception as e:
            self.logger.warning("Unhandled exception in main loop", exc_info=True)
            self.stop(False)
            if self.pidfile is not None:
                self.pidfile.unlink()
            sys.exit(-1)
