#! /usr/bin/env python
# -*- coding: utf-8 -*-
# >>
#     gevent-tasks, 2017
# <<

import logging

from crontab import CronTab

from gevent_tasks.manager import TaskManager
from gevent_tasks.tasks import Task

logger = logging.getLogger("gevent_tasks")
logger.addHandler(logging.NullHandler())

# alias
cron = CronTab

__all__ = ["Task", "TaskManager", "cron"]
