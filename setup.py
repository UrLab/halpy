from setuptools import setup

setup(
    name='halpy',
    version='0.2',
    description="""
        halpy is a high-level Python API for the HAL project. HAL is an
        arduino-based human-hackerspace interface, meant to be reusable and
        easy to use.
    """,
    url='',
    author='UrLab',
    author_email='',
    license='Beerware',
    packages=['halpy'],

    # Put package dependencies here (list of strings)
    install_requires=[],
    zip_safe=False,

    # Put here command line scripts (usually located in bin/; list of strings)
    scripts=[],
)
