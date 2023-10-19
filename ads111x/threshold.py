"""
description: configure threashold modes
"""

import click

from typing import Tuple, Optional
from smbus2 import SMBus

from .config import get_config, gain_to_lsb, get_lsb
from .common import conversion_value, cli
from .log import get_logger


LOG = get_logger()


def get_thresholds(bus: SMBus, addr: int) -> Optional[Tuple[float, float]]:
    """return (Lo_thresh, Hi_thresh) values"""

    lsb = get_lsb(bus, addr)

    lo = conversion_value(bus.read_i2c_block_data(addr, 0b10, 2))
    hi = conversion_value(bus.read_i2c_block_data(addr, 0b11, 2))
    if (not lo) or (not hi):
        LOG.error("Failed to get Lo_thresh/Hi_thres from device: %r, %r", lo, hi)
        return None

    return (lsb*lo, lsb*hi)


@cli.command("get-thresholds")
@click.pass_context
def _(ctx):
    ctx.ensure_object(dict)
    addr = ctx.obj["addr"]

    try:
        with SMBus(ctx.obj["bus"]) as bus:
            res = get_thresholds(bus, addr)
            if not res:
                LOG.error("Failed to get thresholds")
                return 1
            (l, h) = res
            LOG.log(31, "Lo_thresh = %.2f, Hi_thresh = %.2f", l, h)
        return 0
    except Exception as err:
        LOG.error("Failed to get thresholds: %s", err)
        raise

