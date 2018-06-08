#! /usr/bin/env python
# -*- coding: utf-8 -*-
# >>
#     gevent-tasks, 2017
# <<

import re

import random
import string

CHARS = string.ascii_letters + string.digits
UNDER_RE = re.compile(r"(_+[\w|\d])", re.I)


def gen_uuid(length=4):
    """Generate a random ID of a given length.

    Args:
        length (int): length of the returned string.

    Returns:
        `str` of length ``length``.

    Example::

        >>> gen_uuid()
        aB6z
        >>> gen_uuid(10)
        aAzZ0123mN
        >>> gen_uuid(None)
        9
    """
    if not length or length < 1:
        length = 1
    return "".join(map(lambda c: random.choice(CHARS), range(length)))


def convert_fn_name(name):
    """Converts underscore named functions to CamelCase.

    Args:
        name (str): the name of a function; or any string.

    Returns:
        :py:`str`

    Example::

        >>> convert_fn_name('some_function')
        SomeFunction
        >>> convert_fn_name('_some__function')
        SomeFunction
        >>> convert_fn_name('')
        Function
    """
    if not name:
        return "Function"
    name = name[0].upper() + name[1:]
    for c in UNDER_RE.findall(name):
        x = c.strip("_").upper()
        name = name.replace(c, x)
    return name
