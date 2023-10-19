"""
description: continuous conversion data capture
"""

import click

from typing import Optional
from smbus2 import SMBus
from time import sleep
from signal import signal, SIGQUIT

from .common import cli
from .config import modify_config, Mode, ModeE, get_config, gain_to_lsb, get_lsb, ComparatorQueue, ComparatorQueueE
from .single_shot import get
from .log import get_logger

LOG = get_logger()


def is_running(bus: SMBus, addr: int):
    """
    read OS bit from device:
    0 : Device is currently performing a conversion
    1 : Device is not currently performing a conversion
    """
    return bool(bus.read_i2c_block_data(addr, 1, 1)[0] >> 7)


def run(bus: SMBus, addr: int):
    """setup device for performing conversion"""
    modify_config(bus, addr, mode=Mode(ModeE.CONVERSION))


def enable_ready_pin_mode(bus: SMBus, addr: int):
    """
    The ALERT/RDY pin can also be configured as a conversion ready pin. Set the most-significant bit of the
    Hi_thresh register to 1 and the most-significant bit of Lo_thresh register to 0 to enable the pin as a conversion
    ready pin. The COMP_POL bit continues to function as expected. Set the COMP_QUE[1:0] bits to any 2-bit
    value other than 11 to keep the ALERT/RDY pin enabled, and allow the conversion ready signal to appear at the
    ALERT/RDY pin output. The COMP_MODE and COMP_LAT bits no longer control any function. When
    configured as a conversion ready pin, ALERT/RDY continues to require a pullup resistor.
    """
    bus.write_i2c_block_data(addr, 0b10, [0, 0])
    bus.write_i2c_block_data(addr, 0b11, [1 << 7, 0])

    modify_config(bus, addr, comp_que=ComparatorQueue(ComparatorQueueE.ONE))


@cli.command("is-running")
@click.pass_context
def _(ctx):
    ctx.ensure_object(dict)

    with SMBus(ctx.obj["bus"]) as bus:
        x = is_running(bus, ctx.obj["addr"])
        LOG.log(31, ("" if x else "is not ") + "running")
        return int(not x)


class ExitFlag:
    value = False

    def __bool__(self):
        return self.value


@cli.command("run")
@click.pass_context
@click.option("--ready-pin", "-p", type=int)
def _(ctx, ready_pin: Optional[int]):
    ctx.ensure_object(dict)
    addr = ctx.obj["addr"]

    # setup exit signal
    exit_flag = ExitFlag()

    def exit_hlr(sig_no, frame):
        print("Exit signal received")
        del sig_no, frame
        ExitFlag.value = True

    signal(SIGQUIT, exit_hlr)


    with SMBus(ctx.obj["bus"]) as bus:

        # setup pins
        if ready_pin is not None:
            enable_ready_pin_mode(bus, addr)

            from RPi import GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(ready_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        lsb = get_lsb(bus, addr)
        run(bus, addr)

        while not exit_flag:
            print( get(bus, addr, lsb) )

            if ready_pin is not None:
                GPIO.wait_for_edge(ready_pin, GPIO.FALLING)
            else:
                sleep(0.1)


