# Copyright UrLab 2014-2015
# Florentin Hennecker, Nikita Marchant, Titouan Christophe

from os import path, listdir
from .simple_inotify import InotifyWatch
import socket
import asyncio


class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


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

    def on_change(self, func):
        pattern = type(self), self.name
        installed = self.hal.change_events.get(pattern, [])
        self.hal.change_events[pattern] = installed + [func]


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
            try:
                entries = listdir(path.join(self.halfs_root, name))
                resources = AttrDict({e: klass(self, e) for e in entries})
                setattr(self, name, resources)
            except FileNotFoundError:
                continue
        self.running = False
        self.trigger_events = {}
        self.change_events = {}

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
        parts = [x.strip('/') for x in parts]
        return self.resource_mapping[parts[0]](self, parts[1])

    def run(self):
        loop = asyncio.get_event_loop()

        # Socket for triggers
        events_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        events_sock.connect(path.join(self.halfs_root, "events"))

        def dispatch_events():
            text = ''
            while not text.endswith('\n'):
                text += events_sock.recv(1).decode()

            name, statestr = text.strip().split(':')
            state = statestr == '1'

            for n in [name, None]:
                for s in [state, None]:
                    for handler in self.trigger_events.get((n, s), []):
                        loop.run_in_executor(None, handler, name, state)

        # Inotify for changes
        watcher = InotifyWatch(self.halfs_root)

        def dispatch_changes():
            changed_file = watcher.get()
            resource = self.map_path(changed_file)
            pattern = type(resource), resource.name

            for handler in self.change_events.get(pattern, []):
                loop.run_in_executor(None, handler, resource)

        loop.add_reader(events_sock, dispatch_events)
        loop.add_reader(watcher.fd, dispatch_changes)

        loop.run_forever()

    def on_trigger(self, match_name=None, match_state=None):
        if match_state is not None:
            match_state = bool(match_state)
        pattern = (match_name, match_state)

        installed = self.trigger_events.get(pattern, [])

        def wrapper(func):
            self.trigger_events[pattern] = installed + [func]
        return wrapper
