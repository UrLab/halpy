# HALpy

A high-level Python API for [HAL driver](http://github.com/urlab/hal-driver)
running in asyncio

## Usage

```python
import asyncio
from halpy import HAL

hal = HAL("/tmp/hal")


# Register a function to be executed each time the power output is changed
@hal.switchs.power.on_change
def power_change(power):
    print("Power", "on" if power.on else "off")


# Register a function to be executed each time the button is pressed down
@hal.on_trigger('button', True)
def button_pressed(*args, **kwargs):
    hal.switchs.power.on = True
    yield from asyncio.sleep(5)
    hal.switchs.power.on = False


# This decorator is equivalent to the previous one
# Register a function to be executed each time the button is released
@hal.triggers.button.on_trigger(False)
def button_released(*args):
    print("Button released")


# Register a function to be called for every trigger
@hal.on_trigger()
def log_all(name, state):
    print("EVENT", name, "->", state)


if __name__ == "__main__":
    # Run mainloop in asyncio default event loop
    hal.run()
```
