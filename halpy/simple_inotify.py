import ctypes as C
import os
from struct import unpack
from collections import namedtuple


libc = C.CDLL("libc.so.6")
IN_CLOSE_WRITE = 0x08  # Better: parse sys/inotify.h


class SimpleINotifyError(Exception):
    pass


struct_inotify_event = namedtuple('inotify_event', 'wd mask cookie len')


class InotifyWatch(object):
    def __init__(self, directory):
        self.followed = {}
        self.fd = libc.inotify_init()
        if self.fd < 0:
            raise SimpleINotifyError("Unable to initialize inotify")

        for root, dirs, files in os.walk(directory):
            for f in files:
                full_path = os.path.join(root, f)

                r = libc.inotify_add_watch(
                    self.fd,
                    C.c_char_p(bytes(full_path.encode())),
                    C.c_int(IN_CLOSE_WRITE))
                if r < 0:
                    raise SimpleINotifyError("Unable to follow %s: %d" % (
                        full_path, r))
                self.followed[r] = full_path

    def get(self):
        buf = os.read(self.fd, 16)
        if len(buf) == 16:
            event = struct_inotify_event._make(unpack('iIII', buf))
            # Read name length bytes
            if event.len > 0:
                os.read(self.fd, event.len)
            return self.followed[event.wd]
