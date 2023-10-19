"""
description: pretty logging
"""

import os
import sys
import colorama as cl

from typing import Optional, Any
from functools import partial
from logging import getLogger, Logger, Formatter
from logging import WARNING
from logging import StreamHandler
from datetime import datetime as dt
from collections import defaultdict


DEFAULT_LOGGER_NAME = ""


def colored(back: str, fore: str, text: Any):
    return back + fore + str(text) + cl.Fore.RESET + cl.Back.RESET


text_normal = partial(colored, cl.Back.LIGHTBLACK_EX, cl.Fore.LIGHTWHITE_EX)
text_thread = partial(colored, cl.Back.CYAN, cl.Fore.BLACK)
text_process = partial(colored, cl.Back.LIGHTBLUE_EX, cl.Fore.BLACK)
text_trace = partial(colored, cl.Back.LIGHTBLACK_EX, cl.Fore.LIGHTGREEN_EX)


text_level_mapper = defaultdict( lambda: partial(colored, cl.Back.WHITE, cl.Fore.BLACK), {
    "debug": partial(colored, cl.Back.BLUE, cl.Fore.LIGHTWHITE_EX),
    "info": partial(colored, cl.Back.MAGENTA, cl.Fore.LIGHTWHITE_EX),
    "warning": partial(colored, cl.Back.YELLOW, cl.Fore.LIGHTWHITE_EX),
    "error": partial(colored, cl.Back.RED, cl.Fore.LIGHTWHITE_EX),
    "critical": partial(colored, cl.Back.LIGHTRED_EX, cl.Fore.LIGHTWHITE_EX),
})


class ColoredLogFormatter(Formatter):
    """A colorful logger with text output and trace data output
    """

    def __init__(self, datefmt=None):
        self.main_pid = os.getpid()
        super().__init__(fmt="%(message)s", datefmt=datefmt)

    def format(self, record):
        message = text_normal(record.getMessage())
        thread_name = record.threadName
        if thread_name != "MainThread":
            thread = text_thread(thread_name)
        else:
            thread = ""

        indent = ""

        if self.main_pid != record.process:
            process = text_process(f"PID{record.process}")
        else:
            process = ""

        cur_time = cl.Back.LIGHTBLUE_EX + cl.Fore.WHITE + dt.now().isoformat() + cl.Fore.RESET + cl.Back.RESET

        path_name = text_trace(record.pathname)
        func_name = text_trace(record.funcName)
        line_no = text_trace(record.lineno)

        level_name = text_level_mapper[record.levelname.lower()](f"{record.levelname:^10.10}")

        message = (
            f"{indent}{cur_time} "
            f"{path_name}.{func_name}:{line_no}\n"
            f"{process}{thread}{level_name} {message}"
        )

        return message


def get_logger(logger_name: Optional[str] = None) -> Logger:
    """Returns a default logger"""
    return getLogger(logger_name or DEFAULT_LOGGER_NAME)


def enable(level: Optional[int] = None, logger_name: Optional[str] = None):
    """
    Enable logger with the output to stderr stream
    """
    formatter = ColoredLogFormatter()
    logger = get_logger(logger_name)

    level = level or WARNING
    assert 0 <= level <= 50

    handler = StreamHandler(sys.stderr)
    handler.setLevel(level)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    logger.setLevel(level or 0)


def test_logger():
    from threading import Thread
    from multiprocessing import Process

    enable(1)
    log = get_logger()

    def f():
        log.debug("debug enabled")
        log.info("info enabled")
        log.warning("warning enabled")
        log.error("error enabled")
        log.critical("critical enabled")
        log.log(31, "log (31) enabled")

    f()

    thread = Thread(target=f)
    process = Process(target=f)

    thread.start()
    thread.join()

    process.start()
    process.join()


    def g():
        thread = Thread(target=f)
        thread.start()
        thread.join()

    process = Process(target=g)
    process.start()
    process.join()

