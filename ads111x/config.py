#!/bin/python3
"""
description: ADS1115 python wrapper

```python
"_".join(map(lambda x: "{0:08b}".format(x),  bus.read_i2c_block_data(0x48, 1, 2)))
```

```python
bus.write_i2c_block_data(0x48, 1, bytes([0b10000100,  0b10000011]))
```
"""
from __future__ import annotations

import sys
import click
import struct

from typing import Optional
from smbus2 import SMBus
from signal import SIGQUIT, signal
from time import sleep
from enum import Enum
from dataclasses import dataclass, field, asdict, replace
from pprint import pprint, pformat

from .common import cli
from .log import get_logger

LOG = get_logger()


class SerializationError(Exception):
    pass

class DeserializationError(Exception):
    pass


class AIn(Enum):
    Gnd = -1
    AIn_0 = 0
    AIn_1 = 1
    AIn_2 = 2
    AIn_3 = 3


# ( 0bXXX, AIn_P, AIn_N )
multiplexer_mapper: set[tuple[int, AIn, AIn]] = {
    (0b000, AIn.AIn_0, AIn.AIn_1),
    (0b001, AIn.AIn_0, AIn.AIn_3),
    (0b010, AIn.AIn_1, AIn.AIn_3),
    (0b011, AIn.AIn_2, AIn.AIn_3),
    (0b100, AIn.AIn_0, AIn.Gnd),
    (0b101, AIn.AIn_1, AIn.Gnd),
    (0b110, AIn.AIn_2, AIn.Gnd),
    (0b111, AIn.AIn_3, AIn.Gnd)
}


@dataclass(frozen = True)
class Multiplexer:
    """
    Input multiplexer configuration (ADS1115 only)
    """
    AIn_P: AIn = AIn.AIn_0
    AIn_N: AIn = AIn.AIn_1

    def ser(self):
        for (x, p, n) in multiplexer_mapper:
            if p == self.AIn_P and n == self.AIn_N:
                return x << 12

        raise SerializationError(f"{self.AIn_P=}, {self.AIn_N=}")


    @classmethod
    def deser(cls, x: int):
        y = (x >> 12) & 0b111
        for (x, p, n) in multiplexer_mapper:
            if y == x:
                return cls(p, n)

        raise DeserializationError(f"{x=}")


class GainE(Enum):
    """
    Full-Scale Range (FSR)  of the programmable gain amplifier
    | FSR      | LSB SIZE  |
    | ---      | ---       |
    | ±6.144 V | 187.5 μV  |
    | ±4.096 V | 125 μV    |
    | ±2.048 V | 62.5 μV   |
    | ±1.024 V | 31.25 μV  |
    | ±0.512 V | 15.625 μV |
    | ±0.256 V | 7.8125 μV |
    """
    SGN_6P144 = 0b000
    SGN_4P096 = 0b001
    SGN_2P048 = 0b010  # default
    SGN_1P024 = 0b011
    SGN_0P512 = 0b100
    SGN_0P256 = 0b101


def gain_to_lsb(gain_e: GainE):
    if gain_e == GainE.SGN_6P144:
        return 187.5
    if gain_e == GainE.SGN_4P096:
        return 125.0
    if gain_e == GainE.SGN_2P048:
        return 62.5
    if gain_e == GainE.SGN_1P024:
        return 31.25
    if gain_e == GainE.SGN_0P512:
        return 15.625
    if gain_e == GainE.SGN_0P256:
        return 7.8125

    raise ValueError(f"{gain_e}")


@dataclass(frozen=True)
class Gain:
    """Wraps `GainE`"""
    value: GainE = GainE.SGN_2P048

    def ser(self):
        return self.value.value << 9

    @classmethod
    def deser(cls, x: int):
        return cls( GainE( (x >> 9) & 0b111 ) )


class ModeE(Enum):
    """Device operating mode"""
    CONVERSION = 0
    SINGLESHOT = 1  # default


@dataclass(frozen=True)
class Mode:
    value: ModeE = ModeE.SINGLESHOT

    def ser(self):
        return self.value.value << 8

    @classmethod
    def deser(cls, x):
        return cls( ModeE( (x >> 8) & 0b1 ) )


class DataRateE(Enum):
    """Data rate"""
    SPS_8 = 0b000
    SPS_16 = 0b001
    SPS_32 = 0b010
    SPS_64 = 0b011
    SPS_128 = 0b100  # (default)
    SPS_250 = 0b101
    SPS_475 = 0b110
    SPS_860 = 0b111

@dataclass(frozen=True)
class DataRate:
    value: DataRateE = DataRateE.SPS_128

    def ser(self):
        return self.value.value << 5

    @classmethod
    def deser(cls, x):
        return cls( DataRateE( (x >> 5) & 0b111 ) )


class ComparatorModeE(Enum):
    """
    Comparator mode (ADS1114 and ADS1115 only)

    In traditional comparator mode, the ALERT/RDY pin asserts (active low by default) when conversion data exceeds the
    limit set in the high-threshold register (Hi_thresh). The comparator then deasserts only when the conversion data
    falls below the limit set in the low-threshold register (Lo_thresh). In window comparator mode, the ALERT/RDY pin
    asserts when the conversion data exceed the Hi_thresh register or fall below the Lo_thresh register value.
    """
    TRADITIONAL = 0  # default
    WINDOW = 1

@dataclass(frozen=True)
class ComparatorMode:
    value: ComparatorModeE = ComparatorModeE.TRADITIONAL

    def ser(self):
        return self.value.value << 4

    @classmethod
    def deser(cls, x):
        return cls(ComparatorModeE( (x >> 4) & 0b1 ))


class ComparatorPolarityE(Enum):
    """
    Comparator polarity (ADS1114 and ADS1115 only)
    This bit controls the polarity of the ALERT/RDY pin.
    """
    LOW = 0  # default
    HIGH = 1

@dataclass(frozen=True)
class ComparatorPolarity:
    value: ComparatorPolarityE = ComparatorPolarityE.LOW

    def ser(self):
        return self.value.value << 3

    @classmethod
    def deser(cls, x):
        return cls(ComparatorPolarityE( (x >> 3) & 0b1 ))


class ComparatorLatchingE(Enum):
    """
    Latching comparator (ADS1114 and ADS1115 only)

    In either window or traditional comparator mode, the comparator can be configured to latch after being asserted
    by the COMP_LAT bit in the Config register. This setting causes the assertion to remain even if the input signal
    is not beyond the bounds of the threshold registers. This latched assertion can only be cleared by issuing an
    SMBus alert response or by reading the Conversion register.
    """
    # The ALERT/RDY pin does not latch when asserted
    NO = 0  # default
    # The asserted ALERT/RDY pin remains latched until conversion data are read by the master or an appropriate 
    # SMBus alert response is sent by the master. The device responds with its address, and it is the lowest address
    # currently asserting the ALERT/RDY bus line.
    YES = 1

@dataclass(frozen=True)
class ComparatorLatching:
    value: ComparatorLatchingE = ComparatorLatchingE.NO

    def ser(self):
        return self.value.value << 2

    @classmethod
    def deser(cls, x):
        return cls(ComparatorLatchingE( ( x >> 2 ) & 0b1 ))


class ComparatorQueueE(Enum):
    """
    Comparator queue and disable (ADS1114 and ADS1115 only)

    The comparator can also be configured to activate the ALERT/RDY pin only after a set number of successive
    readings exceed the threshold values set in the threshold registers (Hi_thresh and Lo_thresh).
    The COMP_QUE[1:0] bits in the Config register configures the comparator to wait for one, two, or four readings
    beyond the threshold before activating the ALERT/RDY pin. The COMP_QUE[1:0] bits can also disable the
    comparator function, and put the ALERT/RDY pin into a high state.
    """
    ONE = 0b00
    TWO = 0b01
    FOUR = 0b10
    DISABLED = 0b11  # default

@dataclass(frozen=True)
class ComparatorQueue:
    value: ComparatorQueueE = ComparatorQueueE.DISABLED

    def ser(self):
        return self.value.value

    @classmethod
    def deser(cls, x):
        return cls(ComparatorQueueE( x & 0b11 ))


@dataclass(frozen=True)
class ConfigD:
    mux: Multiplexer = field(default_factory = Multiplexer)
    pga: Gain = field(default_factory = Gain)
    mode: Mode = field(default_factory = Mode)
    dr: DataRate = field(default_factory = DataRate)
    comp_mode: ComparatorMode = field(default_factory = ComparatorMode)
    comp_pol: ComparatorPolarity = field(default_factory = ComparatorPolarity)
    comp_lat: ComparatorLatching = field(default_factory = ComparatorLatching)
    comp_que: ComparatorQueue = field(default_factory = ComparatorQueue)


@dataclass(frozen=True, repr=False)
class Config:
    value: ConfigD = field(default_factory = ConfigD)

    def ser(self):
        return sum( [ getattr(self.value, k).ser() for k in dir(self.value) if not k.startswith("_") ] )

    @classmethod
    def deser(cls, x):
        return cls(ConfigD(
            mux=Multiplexer.deser(x),
            pga=Gain.deser(x),
            mode=Mode.deser(x),
            dr=DataRate.deser(x),
            comp_mode=ComparatorMode.deser(x),
            comp_pol=ComparatorPolarity.deser(x),
            comp_lat=ComparatorLatching.deser(x),
            comp_que=ComparatorQueue.deser(x)))

    def __repr__(self):
        return repr(self.value)


def get_config(bus: SMBus, addr: int):
    """
    read register `01`
    """
    return Config.deser( int.from_bytes( bytes(bus.read_i2c_block_data(addr, 1, 2)), 'big' ) )


def set_config(bus: SMBus, addr: int, cfg: Config):
    """
    write register `01`
    """
    # cfg_ = get_config(bus, addr)
    x = cfg.ser()
    bus.write_i2c_block_data(addr, 1, [x >> 8, x & 0xff])


def modify_config(bus: SMBus, addr: int, **kw):
    """
    modify existing config
    """
    cfg = Config(replace(
        get_config(bus, addr).value,
        **kw
    ))
    set_config(bus, addr, cfg)


def get_lsb(bus: SMBus, addr: int):
    """get current LSB from config"""
    return gain_to_lsb(get_config(bus, addr).value.pga.value)


def test_config():

    val = 0b00000101_10000011
    assert Config().ser() == val
    assert Config.deser(val) == Config()
    assert Config.deser(Config().ser()) == Config()



@cli.command("get-config")
@click.pass_context
def _(ctx):
    ctx.ensure_object(dict)
    with SMBus(ctx.obj["bus"]) as bus:
        LOG.log(31, pformat(asdict(get_config(bus, ctx.obj["addr"]))))

@cli.command("modify-config")
@click.pass_context
@click.option(
    "--multiplexer", "-m",
    type=click.Tuple([click.Choice(list(AIn.__members__.keys())), click.Choice( list(AIn.__members__.keys()) ) ]),
    callback=lambda _, __, v: Multiplexer(getattr(AIn, v[0]), getattr(AIn, v[1])) if v else None)
@click.option(
    "--pga", "-g",
    type=click.Choice(list(GainE.__members__.keys())),
    callback=lambda _, __, v: Gain(getattr(GainE, v)) if v else None)
@click.option(
    "--mode", "-d",
    type=click.Choice(list(ModeE.__members__.keys())),
    callback=lambda _, __, v: Mode(getattr(ModeE, v)) if v else None)
@click.option(
    "--dr", "-r",
    type=click.Choice(list(DataRateE.__members__.keys())),
    callback=lambda _, __, v: DataRate(getattr(DataRateE, v)) if v else None)
@click.option(
    "--comp-mode",
    type=click.Choice(list(ComparatorModeE.__members__.keys())),
    callback=lambda _, __, v: ComparatorMode(getattr(ComparatorModeE, v)) if v else None)
@click.option(
    "--comp-pol",
    type=click.Choice(list(ComparatorPolarityE.__members__.keys())),
    callback=lambda _, __, v: ComparatorPolarity(getattr(ComparatorPolarityE, v)) if v else None)
@click.option(
    "--comp-lat",
    type=click.Choice(list(ComparatorLatchingE.__members__.keys())),
    callback=lambda _, __, v: ComparatorLatching(getattr(ComparatorLatchingE, v)) if v else None)
@click.option(
    "--comp-que",
    type=click.Choice(list(ComparatorQueueE.__members__.keys())),
    callback=lambda _, __, v: ComparatorQueue(getattr(ComparatorQueueE, v)) if v else None)
def _(ctx, **kwargs):
    ctx.ensure_object(dict)

    # cfg = Config(ConfigD())
    # LOG.info(pformat(asdict(cfg)))
    # x = cfg.ser()
    # LOG.debug(bin(x))
    # LOG.debug([f"{(x >> 8):>08b}",  f"{(x & 0xff):>08b}"])

    with SMBus(ctx.obj["bus"]) as bus:
        modify_config(bus, ctx.obj["addr"], **{k: v for k, v in kwargs.items() if v is not None})
        # bus.write_i2c_block_data(ctx.obj["addr"], 1, [x >> 8, x & 0xff])



