#! /usr/bin/env python
# -*- coding: utf-8 -*-
# >>
#     gevent-tasks, 2017
# <<

import random
import string

ch_choices = string.ascii_letters + string.digits


def gen_uuid(length=4):
    # type: (int) -> str
    """ Generate a random ID of a given length. """
    return ''.join(map(lambda c: random.choice(ch_choices), range(length)))
