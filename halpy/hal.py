# Copyright UrLab 2014-2015
# Florentin Hennecker, Nikita Marchant, Titouan Christophe

from datetime import datetime
from os import path, listdir
from .simple_inotify import InotifyWatch
from io import FileIO
import socket
import asyncio
import warnings
from logging import getLogger

log = getLogger(__name__)


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
    Base class for all HAL resources (switchs, anims, triggers, sensors, rgbs).
    You shouldn't instanciate a resource by yourself
    (this is done by a HAL instance)
    """
    hal_type = ''

    def __init__(self, hal, name):
        if not self.hal_type:
            raise RuntimeError("Cannot instanciate abstract resource !")
        self.hal = hal
        self.name = name

    def read(self, *path, **kwargs):
        """Read a driver file that belongs to this resource"""
        full_path = (self.hal_type, self.name) + path
        return self.hal.read(*full_path, **kwargs)

    def write(self, value, *path, **kwargs):
        """Write a driver file that belongs to this resource"""
        full_path = (self.hal_type, self.name) + path
        return self.hal.write(value, *full_path, **kwargs)

    def on_change(self, func):
        """
        Register a callback to be executed everytime this resource is modified

        :Example:

        >>> @resource.on_change
        >>> def resource_has_changed(resource):
        >>>     print(resource.name + " has changed")
        """
        pattern = type(self), self.name
        installed = self.hal.change_events.get(pattern, [])
        self.hal.change_events[pattern] = installed + [asyncio.coroutine(func)]
        return func


class Animation(Resource):
    """
    A PWM output that can vary over time. An animation has frames
    (the PWM values), which are played at a certain speed. If the animation is
    looping, when the last frame has been played, it returns to the first one,
    otherwise it stops.
    """

    hal_type = "animations"

    @property
    def fps(self):
        """Return the animation speed in frames per second"""
        return self.read("fps")

    @fps.setter
    def fps(self, value):
        """Set the animation speed, in frames per second"""
        value = int(value)
        assert 4 <= value <= 1024
        return self.write("%d" % value, "fps")

    @property
    def playing(self):
        """Return a boolean indicating whether the animation is playing"""
        return self.read("play") == '1'

    @playing.setter
    def playing(self, value):
        """Set to true to play the animation"""
        self.write("1" if value else "0", "play")

    @property
    def looping(self):
        """Return a boolean indicating whether the animation is looping"""
        return self.read("loop") == '1'

    @looping.setter
    def looping(self, value):
        """Set to true to make the animation looping"""
        self.write("1" if value else "0", "loop")

    @property
    def frames(self):
        """Return the PWM values, as a list of integers"""
        return list(self.read("frames", binary=True))

    @frames.setter
    def frames(self, value):
        """
        Set the animation PWM values (at most 255), which are either integers
        in the range [0, 255] or floats in the range [0, 1]

        :Example:

        >>> anim.frames = [255, 128, 0, 128]
        >>> anim.frames = [1.0, 0.5, 0, 0.5]
        """
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
        """Old API for animation.frames = ..."""
        warnings.warn(
            "Animation.upload is deprecated. Please use Animation.frames=",
            DeprecationWarning)
        self.frames = frames


class Switch(Resource):
    """
    A binary output
    """
    hal_type = 'switchs'

    @property
    def on(self):
        """Return a boolean indicating is the output is active or not"""
        return self.read().strip() == "1"

    @on.setter
    def on(self, value):
        """Activate the output if set to True"""
        self.write("1" if value else "0")


class Rgb(Resource):
    """
    A set of 3 outputs that are connected to an RGB led. If connected to PWM
    output, there are 2^24 different colors (1 byte for R, G and B), if
    connected to binary output, there are 8 different colors (R, G and B could
    be active or not); this is determined by the Arduino firmware.
    """
    hal_type = 'rgbs'

    @property
    def css(self):
        """Return the actual color as a CSS hex string ('#rrggbb')"""
        return self.read().strip()

    @css.setter
    def css(self, color):
        """Set the actual color with a CSS hex string ('#rgb' or '#rrggbb')"""
        assert color[0] == '#' and (len(color) == 4 or len(color) == 7)
        self.write(color)

    @property
    def color(self):
        """Return the actual color as a tuple of bytes (r, g, b)"""
        css = self.css
        assert css[0] == '#'
        return (int(css[1:3], 16), int(css[3:5], 16), int(css[5:7], 16))

    @color.setter
    def color(self, color):
        """Set the actual color from a tuple of bytes (r, g, b)"""
        intify = lambda x: int(x * 255) if isinstance(x, float) else int(x)
        r, g, b = [max(0, min(255, intify(c))) for c in color]
        self.css = '#%02x%02x%02x' % (r, g, b)


class Trigger(Resource):
    """A binary input"""
    hal_type = 'triggers'

    @property
    def on(self):
        """Return True if the input is active, False otherwise"""
        return self.read().strip() == "1"

    def on_trigger(self, value=None):
        """
        Register a function to be called when the input state changes.
        See also HAL.on_trigger
        """
        return self.hal.on_trigger(self.name, value)


class Sensor(Resource):
    """An analog input"""
    hal_type = 'sensors'

    @property
    def value(self):
        """Return the actual input value (a float between 0 and 1)"""
        return float(self.read().strip('\x00').strip())


class HAL(object):
    """Main HAL class."""

    resource_mapping = {
        c.hal_type: c for c in (Animation, Switch, Trigger, Sensor, Rgb)}

    def __init__(self, halfs_root):
        """Initialize a HAL object, given its Filesystem mountpoint"""
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
        """Expand a filepath inside the driver filesystem"""
        return path.join(self.halfs_root, *filepath)

    def read(self, *filepath, **opts):
        """Returns a string with the content of the file given in parameter"""
        mode = "rb" if opts.get('binary', False) else "r"
        return FileIO(self.expand_path(*filepath), mode).read().strip()

    def write(self, value, *filepath, **opts):
        """Casts value to str and writes it to the file given in parameter"""
        mode = "wb" if opts.get('binary', False) else "w"
        FileIO(self.expand_path(*filepath), mode).write(value)

    def map_path(self, filepath):
        """Return the resource associated to given filepath"""
        parts = path.split(filepath.replace(self.halfs_root, ''))
        while '/' in parts[0][1:]:
            parts = path.split(parts[0])
        parts = [x.strip('/') for x in parts]
        # Currently no resource associated to driver
        if parts[0] == 'driver':
            return
        return self.resource_mapping[parts[0]](self, parts[1])

    def install_loop(self, loop=None):
        """
        Install all callbacks in given asyncio loop
        (or the default event loop if None)
        """
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
                        log.debug(datetime.now(), "CALL", handler.__name__)
                        r = handler(name, state)
                        if asyncio.iscoroutine(r):
                            asyncio.async(r)

        # Inotify for changes
        watcher = InotifyWatch(self.halfs_root)

        def dispatch_changes():
            """Dispatch filesystem writes to user-defined handlers"""
            changed_file = watcher.get()
            resource = self.map_path(changed_file)
            if not resource:
                return
            pattern = type(resource), resource.name

            for handler in self.change_events.get(pattern, []):
                log.debug(datetime.now(), "CALL", handler.__name__)
                r = handler(resource)
                if asyncio.iscoroutine(r):
                    asyncio.async(r)

        if loop is None:
            loop = asyncio.get_event_loop()
        loop.add_reader(events_sock, dispatch_events)
        loop.add_reader(watcher.fd, dispatch_changes)
        return loop

    def run(self, loop=None):
        """
        Run all registred callbacks in given asyncio loop,
        or the default one if None
        """
        loop = self.install_loop()
        loop.run_forever()

    def on_trigger(self, match_name=None, match_state=None):
        """
        Register a function to be called when a trigger change

        :Example:

        >>> @hal.on_trigger()
        >>> def log_all_changes(trigger_name, trigger_active):
        >>>     "This function is called when any trigger changes"
        >>>     print(trigger_name + " changed to " + trigger_active)

        >>> @hal.on_trigger('door')
        >>> def log_door_changes(_, door_active):
        >>>     "This function is called when the door trigger changes"
        >>>     print("Door is " + "open" if door_active else "closed")

        >>> @hal.on_trigger('door', True)
        >>> def log_door_open(*args):
        >>>     "This function is called only when the door opens"
        >>>     print("The door is now open")
        """
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
        """
        Return the total number of bytes received by the driver from the
        Arduino since the driver started
        """
        return int(self.read("driver", "rx_bytes").strip('\x00').strip('\n'))

    @property
    def tx_bytes(self):
        """
        Return the total number of bytes sent by the driver to the
        Arduino since the driver started
        """
        return int(self.read("driver", "tx_bytes").strip('\x00').strip('\n'))

    @property
    def uptime(self):
        """Return the number of elapsed seconds since the driver started"""
        return int(self.read("driver", "uptime").strip('\x00').strip('\n'))

    @property
    def loglevel(self):
        """Return the actual log level of the driver"""
        return int(self.read("driver", "loglevel").strip('\x00').strip('\n'))

    @loglevel.setter
    def loglevel(self, lvl):
        """Set the actual log level of the driver"""
        self.write("%d" % lvl, "driver", "loglevel")
