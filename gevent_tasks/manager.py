#! /usr/bin/env python
# -*- coding: utf-8 -*-
# >>
#     gevent-tasks, 2017
# <<

import re
from typing import List
from logging import Logger, getLogger
from functools import partial
from collections import OrderedDict

from gevent import sleep
from gevent.pool import Pool

from gevent_tasks.tasks import Task, TaskPool

UNDER_RE = re.compile(r'(_+[\w|\d])', re.I)

__all__ = [
    'TaskManager'
]


def _convert_fn_name(name):
    # type: (str) -> str
    """ Converts underscore named functions to CamelCase. """
    name = name[0].upper() + name[1:]
    for c in UNDER_RE.findall(name):
        x = c.strip('_').upper()
        name = name.replace(c, x)
    return name


class TaskManager(object):
    """ Interface for managing tasks and running them in a Gevent Pool. """

    FOREVER_POLL_SECS = 0.5

    def __init__(self, pool=None, logger=None):
        # type: (Pool, Logger, int) -> self

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
        """ Reference to the underlying TaskPool instance. """
        return self._pool

    @property
    def task_names(self):
        # type: () -> List[str]
        """ Copy of a list of all the registered task's names. """
        return [t for t in self._tasks.keys()]

    def add(self, task, start=False):
        # type: (Task, bool) -> None
        """ Add a task to the manager and optionally start executing it. """
        if task.name in self._tasks:
            raise KeyError(task.name)
        if task.pool is None:
            task.pool = self._pool
        self._tasks[task.name] = task
        if start and not task.running:
            task.start()

    def add_many(self, *tasks, start=False):
        # type: (*Task, bool) -> None
        """ Add many tasks to the manager. """
        for task in tasks:
            self.add(task, start=start)

    def start(self, task_name):
        # type: (str) -> None
        """ Start a registered task by name. """
        t = self._tasks.get(task_name, None)
        if t:
            t.start()

    def start_all(self):
        # type: () -> None
        """ Start all registered tasks. """
        for task in self.task_names:
            self.start(task)

    def stop(self, task_name, force=False):
        # type: (str, bool) -> None
        """ Stop a registered task by name. """
        t = self._tasks.get(task_name, None)
        if t:
            t.stop(force)

    def stop_all(self, force=False):
        # type: (bool) -> None
        """ Stop all registered tasks. """
        for task in self.task_names:
            self.stop(task, force)

    def remove_task(self, task, force=False):
        # type: (Task, bool) -> Task
        """ Unregister a task from the manager by name or instance. """
        if hasattr(task, 'name'):
            name = task.name
        else:
            name = task
        t = self._tasks.pop(name, None)
        if t:
            t.stop(force)
        return t

    def remove_all(self, force=True):
        # type: (bool) -> Generator[Task]
        """ Unregister all tasks from the manager. """
        for task in self.task_names:
            yield self.remove_task(task, force)

    def forever(self, *exceptions, stop_after_exc=True, stop_on_zero=True):
        # type: (*Exception) -> bool
        """ Blocks in an infinite loop after starting all registered tasks.
            The only way to break out is if one of the included ``exceptions``
            is raised while being executed in a running task.

            Args:
                exceptions (Exception):
                stop_after_exc (bool):
                stop_on_zero (bool):

            Returns:
                bool
         """
        if not exceptions:
            exceptions = (Exception,)
        self.start_all()
        try:
            while True:
                if stop_on_zero:
                    if self.pool.running == 0 and len(self._tasks) == 0:
                        raise RuntimeError('no tasks can run in pool')
                for t in self:
                    err = t._exc_info
                    if err:
                        if stop_after_exc:
                            exc_cls, exc_val, trace = err
                            self.logger.error(exc_val)
                            raise exc_cls(*exc_val.args)
                        self.remove_task(t.name)
                sleep(self.FOREVER_POLL_SECS)
        except KeyboardInterrupt:
            pass
        except exceptions as e:
            self.logger.exception(e, exc_info=True)
            raise e
        return True
