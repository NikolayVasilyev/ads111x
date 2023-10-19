# ADS111x python tool

A tool and a python package for `I2C` ADCs from Texas Instruments: `ADS1113`, `ADS1114` and `ADS1115`.

The package takes care of device setup for various measurement scenarios:

 * (+) single shot;
 * (+) continuous conversion capture;
 * (+) continuous conversion capture with ready pin read synchronization;
 * (-) continuous conversion capture with thresholds;

## Implementation details

The package may be used as a tool while starting as an executable as follows: `python -m ads111x ...`.
See `python -m ads111x --help` for more info on available commands.

