#! /usr/bin/env python
# -*- coding: utf-8 -*-
# >>
#     gevent-tasks, 2017
# <<

import random
import string

ch_choices = string.ascii_letters + string.digits


def gen_uuid(length=4):
    """ Generate a random ID of a given length.

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
    return ''.join(map(lambda c: random.choice(ch_choices), range(length)))
