# Copyright UrLab 2014
# Florentin Hennecker, Nikita Marchant, Titouan Christophe

import socket
from os import path, listdir
from sys import version_info

from .generators import sinusoid
from .log import getLogger
from .simple_inotify import follow


class HAL(object):
    """Main HAL class."""

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

    def changes(self):
        """
        Return an iterator on all WRITE to HAL parameters.
        """
        return follow(self.halfs_root)

    def sinusoid(self, *args, **kwargs):
        """Compat with old-style API. See halpy.generators.sinusoid"""
        return sinusoid(*args, **kwargs)

    # Sensors
    @property
    def all_sensors(self):
        """List of all sensor names"""
        return listdir(path.join(self.halfs_root, "sensors"))

    def sensor(self, name):
        """Return named sensor value"""
        return self.get(path.join("sensors", name))

    def sensors(self, ):
        """Return all sensors values in a dict"""
        return {name: self.sensor(name) for name in self.all_sensors}

    # Triggers
    @property
    def all_triggers(self):
        """List of all triggers names"""
        return listdir(path.join(self.halfs_root, "triggers"))

    def events(self):
        """
        Subsribe to hal events, and return an iterator (name, state)
        example: for trigger_name, trigger_active in events(): ...
        """
        events = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        events.connect(self.expand_path("events"))
        buf = ""
        while True:
            buf += events.recv(16)
            lines = buf.split('\n')
            buf = lines.pop()
            for line in lines:
                trig_name, state = line.split(':')
                yield trig_name, (state == '1')

    def trig(self, trigger):
        """Return true if trigger is active"""
        return self.get("triggers/" + trigger) == 1

    def waitFor(self, trigger, on_activation=True):
        """Return when trigger becomes (in)active"""
        for trig_name, trig_active in self.events():
            if trig_name == trigger and trig_active == on_activation:
                break

    # Switchs
    @property
    def all_switchs(self):
        """List of all switchs names"""
        return listdir(path.join(self.halfs_root, "switchs"))

    def is_on(self, switch):
        """Return true if given switch is on"""
        return self.get(path.join("switchs", switch)) == 1

    def on(self, switch):
        """Put switch on"""
        self.write(path.join("switchs", switch), 1)

    def off(self, switch):
        """Put switch off"""
        self.write(path.join("switchs", switch), 0)

    # Animations
    @property
    def all_animations(self):
        """List of all animations names"""
        return listdir(path.join(self.halfs_root, "animations"))

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
        self.write(path.join("animations", anim, "frames"), frames)

    def fps(self, anim, fps=None):
        """
        Set anim speed in frames per second.
        If fps is none, only return its actual value
        """
        if fps is None:
            return self.get(path.join("animations", anim, "fps"))
        else:
            assert 4 <= fps <= 1000
            self.write(path.join("animations", anim, "fps"), int(fps))

    def is_playing(self, anim):
        """Return true if anim is currently playing"""
        return self.get(path.join("animations", anim, "play")) == 1

    def play(self, anim):
        """Start playing anim"""
        self.write(path.join("animations", anim, "play"), 1)

    def stop(self, anim):
        """Stop playing anim"""
        self.write(path.join("animations", anim, "play"), 0)

    def is_looping(self, anim):
        """Return true if anim is currently in loop mode"""
        return self.get(path.join("animations", anim, "loop")) == 1

    def loop(self, anim):
        """Put anim in loop mode"""
        self.write(path.join("animations", anim, "loop"), 1)

    def one_shot(self, anim):
        """Put anim in one_shot mode (not playing continuously in loop)"""
        self.write(path.join("animations", anim, "loop"), 0)
