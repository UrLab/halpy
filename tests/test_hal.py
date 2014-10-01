from halpy.hal import HAL


def test_hal():
    hal = HAL("/a/path")
    assert hal.halfs_root == "/a/path"
