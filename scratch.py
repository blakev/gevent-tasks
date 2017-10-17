#! /usr/bin/env python
# -*- coding: utf-8 -*-
# >>
#     gevent-tasks, 2017
# <<

from gevent.monkey import patch_all
patch_all()

from gevent import sleep
from gevent_tasks import TaskManager, Task


def print_hi(task):
    print('hi', task.timing.count, round(task.timing.average, 5))


manager = TaskManager(5)

manager.add(
    Task('HiPrinter', print_hi, interval=1.0)
)

manager.start_all()

while True:
    sleep(0.25)
