"""
description: Single-shot data capture
"""

import click

from smbus2 import SMBus
from dataclasses import replace

from .config import gain_to_lsb, get_config, modify_config, Mode, ModeE, GainE
from .common import conversion_value, cli
from .log import get_logger

LOG = get_logger()


def update(bus: SMBus, addr: int):
    """
    write OS bit to 1:
    Start a single conversion (when in power-down state)
    """
    x = get_config(bus, addr).ser() | (1 << 15)
    bus.write_i2c_block_data(addr, 1, [x >> 8, x & 0xff])


def get(bus: SMBus, addr: int, lsb: float):
    """
    read conversion register
    """
    x = conversion_value(bus.read_i2c_block_data(addr, 0, 2))
    if x is None:
        return None
    return lsb * x


def setup(bus: SMBus, addr: int):
    """
    setup device for single-shot capture
    """
    modify_config(bus, addr, mode = Mode(ModeE.SINGLESHOT))


@cli.command("single-shot")
@click.pass_context
def _(ctx):
    """
    setup device for single shot capture, update and read conversion value
    """
    ctx.ensure_object(dict)
    addr = ctx.obj["addr"]

    LOG.info("Starting capture")

    try:
        with SMBus(ctx.obj["bus"]) as bus:
            setup(bus, addr)
            update(bus, addr)
            print(get(bus, addr, gain_to_lsb(get_config(bus, addr).value.pga.value)))

            LOG.info("Capture success")
        return 0

    except Exception as err:
        LOG.error("Failed: %s", err)
        if __debug__:
            raise
        return 1

