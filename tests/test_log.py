from halpy.log import getLogger


def test_same_logger():
    l1 = getLogger()
    l2 = getLogger()

    assert l1 == l2


def test_different_loggers():
    l1 = getLogger('one')
    l2 = getLogger('other')

    assert l1 != l2
