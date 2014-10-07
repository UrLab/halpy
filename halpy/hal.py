# Copyright UrLab 2014
# Florentin Hennecker, Nikita Marchant, Titouan Christophe

import socket
import glob
from os import path
from sys import version_info

from .generators import sinusoid
from .log import getLogger
from .simple_inotify import follow


class HAL(object):
    def __init__(self, halfs_root):
        self.halfs_root = halfs_root

    def expand_path(self, filename):
        if filename.startswith(self.halfs_root):
            return filename
        return path.join(self.halfs_root, filename)

    def read(self, filename):
        """Returns a string with the content of the file given in parameter"""
        return open(self.expand_path(filename), 'r').read().strip("\0").strip()

    def write(self, filename, value):
        """Casts value to str and writes it to the file given in parameter"""
        open(self.expand_path(filename), 'w').write(str(value))

    def get(self, filename):
        """
        Returns float or int value depending on the type of the value in the
        file
        """
        str_value = self.read(filename)
        if str_value.find(".") == -1:  # value is an integer
            return int(str_value)
        else:  # value is a float
            return float(str_value)
        return 0

    def getLogger(self, *args, **kwargs):
        """Compat with old-style API"""
        return getLogger(*args, **kwargs)

    def events(self):
        """
        Subsribe to hal events, and return an iterator (name, state)
        example: for trigger_name, trigger_active in events(): ...
        """
        events = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        events.connect(self.expand_path("events"))
        while True:
            line = events.recv(16)
            line = line.strip()
            trig_name, state = line.split(':')
            yield trig_name, (state == '1')

    def changes(self):
        """
        Return an iterator on all WRITE to HAL parameters.
        """
        return follow(self.halfs_root)

    def waitFor(self, trigger, on_activation=True):
        """Return when trigger becomes (in)active"""
        for trig_name, trig_active in self.events():
            if trig_name == trigger and trig_active == on_activation:
                break

    def sinusoid(self, *args, **kwargs):
        """Compat with old-style API"""
        return sinusoid(*args, **kwargs)

    def sensor(self, name):
        """Return named sensor value"""
        return self.get("sensors/"+name)

    def sensors(self, ):
        """Return all sensors values in a dict"""
        sensors = {}
        for sensor in glob.glob(path.join(self.halfs_root, "sensors", "*")):
            sensors[path.basename(sensor)] = self.get(sensor)

        return sensors

    def trig(self, trigger):
        """Return true if trigger is active"""
        return self.get("triggers/" + trigger) == 1

    def on(self, switch):
        """Put switch on"""
        self.write("switchs/" + switch, 1)

    def off(self, switch):
        """Put switch off"""
        self.write("switchs/" + switch, 0)

    def upload(self, anim, frames):
        """
        Upload frames to anim.
        Frames could be given in the following formats:
        * [float (0..1), ...]
        * [int (0..255), ...]
        * [chr, ...]
        * str
        """
        assert 0 < len(frames) < 256
        if isinstance(frames, list):
            if isinstance(frames[0], int):
                frames = ''.join(map(chr, frames))
            elif isinstance(frames[0], float):
                frames = ''.join(chr(int(255 * f)) for f in frames)
            elif isinstance(frames[0], str):
                frames = ''.join(frames)
        # Py2/Py3 differences
        if version_info[0] == 2:
            assert type(frames) in (str, unicode, bytes)  # pragma: no flakes
        else:
            assert type(frames) in (str, bytes)
        self.write("animations/" + anim + "/frames", frames)

    def fps(self, anim, fps=None):
        """
        Set anim speed in frames per second.
        If fps is none, only return its actual value
        """
        if fps is None:
            return self.get("animations/" + anim + "/fps")
        else:
            assert 4 <= fps <= 1000
            self.write("animations/" + anim + "/fps", int(fps))

    def play(self, anim):
        """Start playing anim"""
        self.write("animations/" + anim + "/play", 1)

    def stop(self, anim):
        """Stop playing anim"""
        self.write("animations/" + anim + "/play", 0)

    def loop(self, anim):
        """Put anim in loop mode"""
        self.write("animations/" + anim + "/loop", 1)

    def one_shot(self, anim):
        """Put anim in one_shot mode"""
        self.write("animations/" + anim + "/loop", 0)
