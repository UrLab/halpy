# Copyright UrLab 2014-2015
# Florentin Hennecker, Nikita Marchant, Titouan Christophe

from os import path, listdir
from simple_inotify import InotifyWatch
from itertools import chain
import select
import socket


class Resource(object):
    """
    Base class for all HAL resources (switchs, anims, triggers, sensors)
    """
    hal_type = ''

    def __init__(self, hal, name):
        if not self.hal_type:
            raise RuntimeError("Cannot instanciate abstract resource !")
        self.hal = hal
        self.name = name

    def read(self, *path):
        full_path = (self.hal_type, self.name) + path
        return self.hal.read(*full_path)

    def write(self, value, *path):
        full_path = (self.hal_type, self.name) + path
        return self.hal.write(value, *full_path)


class Animation(Resource):
    hal_type = "animations"

    @property
    def fps(self):
        return self.read("fps")

    @fps.setter
    def fps(self, value):
        value = int(value)
        assert 4 <= value <= 1024
        return self.write(value, "fps")

    @property
    def playing(self):
        return self.read("play")

    @playing.setter
    def playing(self, value):
        self.write(1 if value else 0, "play")

    @property
    def looping(self):
        return self.read("loop")

    @looping.setter
    def looping(self, value):
        self.write(1 if value else 0, "loop")


class Switch(Resource):
    hal_type = 'switchs'

    @property
    def on(self):
        return self.read().strip() == "1"

    @on.setter
    def on(self, value):
        self.write(1 if value else 0)


class Trigger(Resource):
    hal_type = 'triggers'

    @property
    def is_active(self):
        return self.read().strip() == "1"


class Sensor(Resource):
    hal_type = 'sensors'

    @property
    def value(self):
        return float(self.read())


class HAL(object):
    """Main HAL class."""

    resource_mapping = {
        c.hal_type: c for c in (Animation, Switch, Trigger, Sensor)}

    def __init__(self, halfs_root):
        self.halfs_root = halfs_root
        for name, klass in self.resource_mapping.items():
            entries = listdir(path.join(self.halfs_root, name))
            setattr(self, name, {e: klass(self, e) for e in entries})

    def expand_path(self, *filepath):
        return path.join(self.halfs_root, *filepath)

    def read(self, *filepath):
        """Returns a string with the content of the file given in parameter"""
        return open(self.expand_path(*filepath), 'r').read().strip()

    def write(self, value, *filepath):
        """Casts value to str and writes it to the file given in parameter"""
        open(self.expand_path(*filepath), 'w').write(str(value))

    def map_path(self, filepath):
        """Return the resource associated to given filepath"""
        parts = path.split(filepath.replace(self.halfs_root, ''))
        while '/' in parts[0][1:]:
            parts = path.split(parts[0])
        parts = map(lambda x: x.strip('/'), parts)
        return self.resource_mapping[parts[0]](self, parts[1])


class EventHAL(HAL):
    """A HAL object with eventloop capabilities"""

    def __init__(self, *args, **kwargs):
        super(EventHAL, self).__init__(*args, **kwargs)
        self.running = False
        self.trigger_events = {}
        self.change_events = {}

    def run(self, poll_timeout_ms=200):
        self.running = True
        poll = select.poll()

        events_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        events_sock.connect(path.join(self.halfs_root, "events"))
        poll.register(events_sock, select.POLLIN)

        changes_watch = InotifyWatch(self.halfs_root)
        poll.register(changes_watch.fd, select.POLLIN)

        while self.running:
            events = poll.poll(poll_timeout_ms)
            for fd, flags in events:
                if fd == changes_watch.fd:
                    self._change_callback(changes_watch.get())
                elif fd == events_sock:
                    line = ''
                    while not line.endswith('\n'):
                        line += events_sock.read(1)
                    self._trigger_callback(line.strip())

    def _change_callback(self, change_path):
        resource = self.map_path(change_path)
        key = (type(resource), resource.name)
        handlers = self.change_events.get(key, tuple())
        for handler in handlers:
            handler(resource)

    def _trigger_callback(self, sock_line):
        name, state = sock_line.split(':')
        state = state == "1"
        handlers = chain(
            self.trigger_events.get((name, state), tuple()),
            self.trigger_events.get((name, None), tuple()))
        for handler in handlers:
            handler(state)

    def on_trigger(self, trig_name, trig_value=None):
        def wrapper(func):
            k = (trig_name, trig_value)
            handlers = self.trigger_events.get(k, tuple())

            def inner(actual_value):
                if trig_value is None or trig_value == actual_value:
                    func(actual_value)
            self.trigger_events[k] = handlers + (inner,)
        return wrapper

    def on_change(self, hal_type, name):
        def wrapper(func):
            k = (hal_type, name)
            handlers = self.change_events.get(k, tuple())

            def inner(resource):
                func(resource)
            self.change_events[k] = handlers + (inner,)
        return wrapper
