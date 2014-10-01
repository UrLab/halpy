from halpy.generators import Note, Silence, Partition, sinusoid


def test_note_defaults():
    n = Note(440)
    assert n.freq == 440
    assert n.duration == 1
    assert n.to_frames() == [44, 44, 44, 0]
    assert n.to_frames(base_duration=1) == [44]


def test_partition_defaults():
    p = Partition(Note(440), Note(494))
    assert p.to_frames() == [44, 44, 44, 0, 49, 49, 49, 0]


def test_partition_with_silence():
    p = Partition(Note(440), Silence(0.5), Note(490))
    assert p.to_frames() == [44, 44, 44, 0, 0, 0, 49, 49, 49, 0]


def test_sinusoid():
    frames = sinusoid(n_frames=4, val_min=0, val_max=10)
    assert frames == [5, 10, 5, 0]


def test_sinusoid_with_floats():
    frames = sinusoid(n_frames=4, val_min=0.0, val_max=10.0/255.0)
    assert frames == [5, 10, 5, 0]
