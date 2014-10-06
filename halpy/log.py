import logging
from os import path
from sys import argv, stdout


def getLogger(name=''):
    """Return a logger suitable for HAL scripts"""

    progname = path.basename(argv[0]).replace('.py', '')
    if name:
        progname += '.' + name

    log = logging.getLogger(progname)
    log.setLevel(logging.DEBUG)

    if len(log.handlers) == 0:
        ch = logging.StreamHandler(stdout)
        ch.setLevel(logging.DEBUG)
        log.addHandler(ch)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        ch.setFormatter(formatter)

    return log
