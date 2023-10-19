"""
description: ADC111x configure and capture tool
"""

import sys

from .common import cli
from . import config  # pyright: ignore
from . import single_shot  # pyright: ignore
from . import conversion  # pyright: ignore
from . import threshold  # pyright: ignore


if __name__ == "__main__":
    sys.exit(cli() or 0)

