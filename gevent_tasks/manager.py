#! /usr/bin/env python
# -*- coding: utf-8 -*-
# >>
#     gevent-tasks, 2017
# <<

import re
from typing import List
from logging import Logger, getLogger
from functools import partial, wraps
from collections import OrderedDict

from gevent.pool import Pool

from gevent_tasks.tasks import Task, TaskPool


UNDER_RE = re.compile(r'(_+[\w|\d])', re.I)


def _convert_fn_name(name):
    # type: (str) -> str
    name = name[0].upper() + name[1:]
    for c in UNDER_RE.findall(name):
        x = c.strip('_').upper()
        name = name.replace(c, x)
    return name


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

    def task(self, _fn=None, **kwargs):
        """ Register a method as a task via decorated function.

            Can be used as a simple decorator, ::

                @manager.task
                def some_function(task):
                    ...

            or with keyword arguments that match those used
            for :obj:`.Task`, ::

                @manager.task(interval=30.0, timeout=25.0)
                def some_function(task):
                    ...

            When keyword arguments are omitted the default values are applied:
            ``name`` is the function's name converted to CamelCase,
            ``timeout`` is 59 seconds, ``interval`` is 60 seconds, and
            ``logger`` is built from the name of the name of
            :obj:`.TaskManager.logger`.


            Args:
                _fn (Callable): function that takes at least one argument,
                    ``task``, that will be run on a fixed interval for the
                    lifetime of the current process.
                kwargs: the same keyword arguments used for creating a
                    :obj:`.Task` object.

            Returns:
                Callable
        """
        def make_task(f, **kw):
            name = kw.get('name', _convert_fn_name(f.__name__))
            kw.update({
                'fn': f,
                'name': name,
                'timeout': kw.get('timeout', 59.0),
                'interval': kw.get('interval', 60.0),
                'logger': kw.get('logger', getLogger(
                    self.logger.name + '.Task.%s' % name))})
            return Task(**kw)

        if _fn and callable(_fn):
            self.add(make_task(_fn))
            return _fn
        else:
            # spec'd out task
            def inner(fn, **kwargs):
                self.add(make_task(fn, **kwargs))
                return fn
            return partial(inner, **kwargs)

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
        if task.pool is None:
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


