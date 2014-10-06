from math import sin, pi
from functools import reduce


class Note(object):
    def __init__(self, freq, duration=1):
        self.freq, self.duration = freq, duration

    def to_frames(self, base_duration=4):
        d = int(self.duration*base_duration)
        f = int(round(float(self.freq)/10))
        if d > 1:
            return [f]*(d-1) + [0]
        return [f]


def Silence(duration=1):
    return Note(0, duration)


class Partition(object):
    def __init__(self, *notes):
        self.notes = notes

    def to_frames(self, base_duration=4):
        return reduce(
            lambda res, n: res + n.to_frames(base_duration), self.notes, []
        )


def sinusoid(n_frames=255, val_min=0, val_max=255):
    """
    Return one sinus period on n_frames varying between val_min and val_max.
    The returned string is suitable for upload()
    """
    if isinstance(val_min, float):
        val_min = 255*val_min
    if isinstance(val_max, float):
        val_max = 255*val_max
    assert val_min <= val_max
    for n in n_frames, val_min, val_max:
        assert 0 <= n < 256

    a = (val_max - val_min) / 2
    m = val_min + a
    return [int(m + a * sin(2 * i * pi / n_frames)) for i in range(n_frames)]
