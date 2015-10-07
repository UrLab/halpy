from halpy import HAL, Animation, Switch, Sensor, Trigger
from os import mkdir, path
from shutil import rmtree

ROOT = path.join('/tmp', 'haltest')


def setup_function(*args, **kwargs):
    mkdir(ROOT)
    for c in (Switch, Trigger, Sensor):
        mkdir(path.join(ROOT, c.hal_type))
        open(path.join(ROOT, c.hal_type, 'test'), 'w').write('0')

    mkdir(path.join(ROOT, Animation.hal_type))
    mkdir(path.join(ROOT, Animation.hal_type, 'test'))
    open(path.join(ROOT, Animation.hal_type, 'test', 'play'), 'w').write('0')
    open(path.join(ROOT, Animation.hal_type, 'test', 'loop'), 'w').write('0')
    open(path.join(ROOT, Animation.hal_type, 'test', 'fps'), 'w').write('25')


def teardown_function(*args, **kwargs):
    rmtree(ROOT)


def test_hal():
    hal = HAL(ROOT)
    assert hal.halfs_root == ROOT
    assert hal.animations.keys() == ['test']
    assert hal.switchs.keys() == ['test']
    assert hal.triggers.keys() == ['test']
    assert hal.sensors.keys() == ['test']


def test_map_full_path():
    hal = HAL(ROOT)
    r = hal.map_path(path.join(ROOT, 'animations/lolilol'))
    assert isinstance(r, Animation)
    assert r.name == 'lolilol'


def test_map_sub_path():
    hal = HAL(ROOT)
    r = hal.map_path('animations/lolilol/play')
    assert isinstance(r, Animation)
    assert r.name == 'lolilol'


def test_map_path():
    hal = HAL(ROOT)
    r = hal.map_path('/animations/lolilol')
    assert isinstance(r, Animation)
    assert r.name == 'lolilol'


def test_rel_path():
    hal = HAL(ROOT)
    r = hal.map_path('animations/lolilol')
    assert isinstance(r, Animation)
    assert r.name == 'lolilol'


def test_switch_on():
    hal = HAL(ROOT)
    assert not hal.switchs['test'].on

    hal.switchs['test'].on = True
    assert hal.switchs['test'].on
    assert open(path.join(ROOT, 'switchs', 'test')).read().strip() == '1'

    hal.switchs['test'].on = False
    assert not hal.switchs['test'].on
    assert open(path.join(ROOT, 'switchs', 'test')).read().strip() == '0'


def test_analog_read():
    hal = HAL(ROOT)
    assert hal.sensors['test'].value == 0.0
