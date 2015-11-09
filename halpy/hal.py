# Copyright UrLab 2014-2015
# Florentin Hennecker, Nikita Marchant, Titouan Christophe

from datetime import datetime
from os import path, listdir
from .simple_inotify import InotifyWatch
import socket
import asyncio
import warnings


class AttrDict(dict):
    """
    A javascript-like dictionary, st.
    a_dict['a_key'] == a_dict.a_key
    """
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

    def read(self, *path, **kwargs):
        full_path = (self.hal_type, self.name) + path
        return self.hal.read(*full_path, **kwargs)

    def write(self, value, *path, **kwargs):
        full_path = (self.hal_type, self.name) + path
        return self.hal.write(value, *full_path, **kwargs)

    def on_change(self, func):
        pattern = type(self), self.name
        installed = self.hal.change_events.get(pattern, [])
        self.hal.change_events[pattern] = installed + [asyncio.coroutine(func)]
        return func


class Animation(Resource):
    hal_type = "animations"

    @property
    def fps(self):
        return self.read("fps")

    @fps.setter
    def fps(self, value):
        value = int(value)
        assert 4 <= value <= 1024
        return self.write("%d" % value, "fps")

    @property
    def playing(self):
        return self.read("play") == '1'

    @playing.setter
    def playing(self, value):
        self.write("1" if value else "0", "play")

    @property
    def looping(self):
        return self.read("loop") == '1'

    @looping.setter
    def looping(self, value):
        self.write("1" if value else "0", "loop")

    @property
    def frames(self):
        return list(self.read("frames", binary=True))

    @frames.setter
    def frames(self, value):
        # Format frames
        intify = lambda x: x if isinstance(x, int) else int(255 * x)
        frames = [intify(x) for x in value]

        # Validation
        if not (0 < len(frames) <= 255):
            raise ValueError("Illegal animation len !")
        for elem in frames:
            if not (isinstance(elem, int) and 0 <= elem <= 255):
                raise ValueError("Illegal value {}".format(elem))

        # Upload !
        self.write(bytes(frames), "frames", binary=True)

    def upload(self, frames):
        warnings.warn(
            "Animation.upload is deprecated. Please use Animation.frames=",
            DeprecationWarning)
        self.frames = frames


class Switch(Resource):
    hal_type = 'switchs'

    @property
    def on(self):
        return self.read().strip() == "1"

    @on.setter
    def on(self, value):
        self.write("1" if value else "0")


class Trigger(Resource):
    hal_type = 'triggers'

    @property
    def on(self):
        return self.read().strip() == "1"

    def on_trigger(self, value=None):
        return self.hal.on_trigger(self.name, value)


class Sensor(Resource):
    hal_type = 'sensors'

    @property
    def value(self):
        return float(self.read().strip('\x00').strip())


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

    def read(self, *filepath, **opts):
        """Returns a string with the content of the file given in parameter"""
        mode = "rb" if opts.get('binary', False) else "r"
        return open(self.expand_path(*filepath), mode).read().strip()

    def write(self, value, *filepath, **opts):
        """Casts value to str and writes it to the file given in parameter"""
        mode = "wb" if opts.get('binary', False) else "w"
        open(self.expand_path(*filepath), mode).write(value)

    def map_path(self, filepath):
        """Return the resource associated to given filepath"""
        parts = path.split(filepath.replace(self.halfs_root, ''))
        while '/' in parts[0][1:]:
            parts = path.split(parts[0])
        parts = [x.strip('/') for x in parts]
        return self.resource_mapping[parts[0]](self, parts[1])

    def run(self, loop=None):
        """Run HAL mainloop in given asyncio event loop"""
        # Socket for triggers
        events_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        events_sock.connect(path.join(self.halfs_root, "events"))

        def dispatch_events():
            """Dispatch trigger events to user-defined handlers"""
            text = ''
            while not text.endswith('\n'):
                text += events_sock.recv(1).decode()

            name, statestr = text.strip().split(':')
            state = statestr == '1'

            for n in [name, None]:
                for s in [state, None]:
                    for handler in self.trigger_events.get((n, s), []):
                        print(datetime.now(), "CALL", handler.__name__)
                        r = handler(name, state)
                        if asyncio.iscoroutine(r):
                            asyncio.async(r)

        # Inotify for changes
        watcher = InotifyWatch(self.halfs_root)

        def dispatch_changes():
            """Dispatch filesystem writes to user-defined handlers"""
            changed_file = watcher.get()
            resource = self.map_path(changed_file)
            pattern = type(resource), resource.name

            for handler in self.change_events.get(pattern, []):
                print(datetime.now(), "CALL", handler.__name__)
                r = handler(resource)
                if asyncio.iscoroutine(r):
                    asyncio.async(r)

        if loop is None:
            loop = asyncio.get_event_loop()
        loop.add_reader(events_sock, dispatch_events)
        loop.add_reader(watcher.fd, dispatch_changes)
        loop.run_forever()

    def on_trigger(self, match_name=None, match_state=None):
        """Register a handler for a trigger change"""
        if match_state is not None:
            match_state = bool(match_state)
        pattern = (match_name, match_state)

        installed = self.trigger_events.get(pattern, [])

        def wrapper(fun):
            self.trigger_events[pattern] = installed + [asyncio.coroutine(fun)]
            return fun
        return wrapper

    @property
    def rx_bytes(self):
        return int(self.read("driver", "rx_bytes"))

    @property
    def tx_bytes(self):
        return int(self.read("driver", "tx_bytes"))

    @property
    def uptime(self):
        return int(self.read("driver", "uptime"))

    @property
    def loglevel(self):
        return int(self.read("driver", "loglevel"))

    @loglevel.setter
    def loglevel(self, lvl):
        self.write("%d" % lvl, "driver", "loglevel")
