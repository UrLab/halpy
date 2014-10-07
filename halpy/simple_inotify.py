import ctypes as C
import os
from struct import unpack
from collections import namedtuple


libc = C.CDLL("libc.so.6")
IN_CLOSE_WRITE = 0x08  # Better: parse sys/inotify.h


class SimpleINotifyError(Exception):
    pass


struct_inotify_event = namedtuple('inotify_event', 'wd mask cookie len')


def follow(directory):
    followed = {}
    fd = libc.inotify_init()
    if fd < 0:
        raise SimpleINotifyError("Unable to initialize inotify")

    for root, dirs, files in os.walk(directory):
        for f in files:
            full_path = os.path.join(root, f)

            r = libc.inotify_add_watch(fd, full_path, IN_CLOSE_WRITE)
            if r < 0:
                raise SimpleINotifyError("Unable to follow " + full_path)
            followed[r] = full_path

    while True:
        buf = os.read(fd, 16)
        if len(buf) == 16:
            event = struct_inotify_event._make(unpack('iIII', buf))
            # Read name length bytes
            if event.len > 0:
                os.read(fd, event.len)
            yield followed[event.wd]
