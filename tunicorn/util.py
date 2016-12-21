import os
import socket
import random
import time

import fcntl
import pwd


def set_non_blocking(fd):
    flags = fcntl.fcntl(fd, fcntl.F_GETFL) | os.O_NONBLOCK
    fcntl.fcntl(fd, fcntl.F_SETFL, flags)


def close_on_exec(fd):
    flags = fcntl.fcntl(fd, fcntl.F_GETFD)
    flags |= fcntl.FD_CLOEXEC
    fcntl.fcntl(fd, fcntl.F_SETFD, flags)


def parse_address(netloc, default_port=8000):
    if netloc.startswith("unix://"):
        return netloc.split("unix://")[1]

    if netloc.startswith("unix:"):
        return netloc.split("unix:")[1]

    if netloc.startswith("tcp://"):
        netloc = netloc.split("tcp://")[1]

    # get host
    if '[' in netloc and ']' in netloc:
        host = netloc.split(']')[0][1:].lower()
    elif ':' in netloc:
        host = netloc.split(':')[0].lower()
    elif netloc == "":
        host = "0.0.0.0"
    else:
        host = netloc.lower()

    # get port
    netloc = netloc.split(']')[-1]
    if ":" in netloc:
        port = netloc.split(':', 1)[1]
        if not port.isdigit():
            raise RuntimeError("%r is not a valid port number." % port)
        port = int(port)
    else:
        port = default_port
    return host, port


def seed():
    try:
        random.seed(os.urandom(64))
    except NotImplementedError:
        random.seed('%s.%s' % (time.time(), os.getpid()))


def set_owner_process(uid, gid, initgroups=False):
    """ set user and group of workers processes """

    if gid:
        if uid:
            try:
                username = get_username(uid)
            except KeyError:
                initgroups = False

        # versions of python < 2.6.2 don't manage unsigned int for
        # groups like on osx or fedora
        gid = abs(gid) & 0x7FFFFFFF

        if initgroups:
            os.initgroups(username, gid)
        else:
            os.setgid(gid)

    if uid:
        os.setuid(uid)


def get_username(uid):
    """ get the username for a user id"""
    return pwd.getpwuid(uid).pw_name


def chown(path, uid, gid):
    gid = abs(gid) & 0x7FFFFFFF  # see note above.
    os.chown(path, uid, gid)

def is_ipv6(addr):
    try:
        socket.inet_pton(socket.AF_INET6, addr)
    except socket.error:  # not a valid address
        return False
    except ValueError:  # ipv6 not supported on this platform
        return False
    return True
