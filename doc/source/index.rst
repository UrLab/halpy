.. HALpy documentation master file, created by
   sphinx-quickstart on Wed Oct  8 00:07:15 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to HALpy's documentation!
=================================

HALpy is a high-level python API for the HAL driver.

Contents:

.. toctree::
   :maxdepth: 2


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

hal
===

:Example:

>>> from halpy import HAL
>>> hal = HAL("/tmp/hal")
>>>
>>> # Register a function to be executed each time the power output is changed
>>> @hal.switchs.power.on_change
>>> def power_change(power):
>>>     print("Power", "on" if power.on else "off")
>>>
>>> # Register a function to be executed each time the button is pressed down
>>> @hal.on_trigger('button', True)
>>> def button_pressed(*args, **kwargs):
>>>     hal.switchs.power.on = True
>>>     yield from asyncio.sleep(5)
>>>     hal.switchs.power.on = False
>>>
>>> # This decorator is equivalent to the previous one
>>> # Register a function to be executed each time the button is released
>>> @hal.triggers.button.on_trigger(False)
>>> def button_released(*args):
>>>     print("Button released")
>>>
>>> # Register a function to be called for every trigger
>>> @hal.on_trigger()
>>> def log_all(name, state):
>>>     print("EVENT", name, "->", state)
>>>
>>> if __name__ == "__main__":
>>>     print("Light inside:", 100*hal.sensors.light_inside.value, '%')
>>>
>>>     # Set ledstrip to this color
>>>     hal.rgbs.ledtrip.css = '#cafeba'
>>>
>>>     # Run mainloop in asyncio default event loop
>>>     hal.run()   

.. automodule:: halpy.hal
    :members:

Generators
==========

.. automodule:: halpy.generators
    :members:
