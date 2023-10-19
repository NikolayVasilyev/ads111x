"""
description: common routines
"""

import click

from typing import List, Optional
from struct import unpack

from .log import get_logger, enable

LOG = get_logger()

def conversion_value(x: List[int]) -> Optional[int]:
    try:
        return unpack(">h", bytes(x))[0]
    except Exception as err:
        LOG.error("failed to unpack value: %r, error:\n%s", x, err)
        return None


@click.group()
@click.pass_context
@click.option("--addr", "-a", required=True, type=click.IntRange(min=0, min_open=False))
@click.option("--bus", "-b", required=True, type=click.IntRange(min=0, min_open=False))
@click.option("--log-level", "-l", type=click.IntRange(min=0, min_open=False, max=50, max_open=False), default=30)
def cli(ctx, addr: int, bus: int, log_level: int):
    ctx.ensure_object(dict)
    enable(log_level)
    ctx.obj["addr"] = addr
    ctx.obj["bus"] = bus

