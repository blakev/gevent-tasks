#! /usr/bin/env python
# -*- coding: utf-8 -*-
# >>
#     gevent-tasks, 2017
# <<

from typing import List
from logging import Logger, getLogger
from collections import OrderedDict

from gevent.pool import Pool

from gevent_tasks.tasks import Task, TaskPool


class TaskManager(object):
    def __init__(self, pool=None, logger=None):
        # type: (Pool, Logger) -> self

        size = None
        if isinstance(pool, int):
            size = pool
        if pool is None:
            size = TaskPool.DEFAULT_POOL_SIZE
        if size is not None:
            pool = TaskPool(size=size)

        self._pool = pool
        self._tasks = OrderedDict()
        self.logger = logger or getLogger('%s.TaskManager' % __name__)

    def __repr__(self):
        return '<TaskManager(tasks=%d,capacity=%d)>' % (
            len(self._tasks), self._pool.size)

    def __iter__(self):
        for task in self._tasks.values():
            yield task

    @property
    def pool(self):
        # type: () -> TaskPool
        return self._pool

    @property
    def task_names(self):
        # type: () -> List[str]
        return [t for t in self._tasks.keys()]

    def add(self, task, start=False):
        # type: (Task, bool) -> None
        if task.name in self._tasks:
            raise KeyError(task.name)
        task.pool = self._pool
        self._tasks[task.name] = task
        if start and not task.is_running:
            task.start()

    def add_many(self, *tasks, start=False):
        # type: (*Task, bool) -> None
        for task in tasks:
            self.add(task, start=start)

    def start(self, task_name):
        # type: (str) -> None
        t = self._tasks.get(task_name, None)
        if t:
            t.start()

    def start_all(self):
        # type: () -> None
        for task in self.task_names:
            self.start(task)

    def stop(self, task_name, force=False):
        # type: (str, bool) -> None
        t = self._tasks.get(task_name, None)
        if t:
            t.stop(force)

    def stop_all(self, force=False):
        # type: (bool) -> None
        for task in self.task_names:
            self.stop(task, force)

    def remove_task(self, task, force=False):
        # type: (Task, bool) -> None
        if hasattr(task, 'name'):
            name = task.name
        else:
            name = task
        t = self._tasks.pop(name, None)
        if t:
            t.stop(force)

    def remove_all(self, force=False):
        # type: (bool) -> None
        for task in self.task_names:
            self.remove_task(task, force)


