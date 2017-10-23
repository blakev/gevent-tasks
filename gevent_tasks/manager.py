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

from gevent_tasks.tasks import Task, TaskPool

UNDER_RE = re.compile(r'(_+[\w|\d])', re.I)

__all__ = [
    'TaskManager'
]


def _convert_fn_name(name):
    # type: (str) -> str
    """ Converts underscore named functions to CamelCase.

    Args:
        name (str): the name of a function; or any string.

    Returns:
        :py:`str`
    """
    name = name[0].upper() + name[1:]
    for c in UNDER_RE.findall(name):
        x = c.strip('_').upper()
        name = name.replace(c, x)
    return name


class TaskManager(object):

    FOREVER_POLL_SECS = 0.5
    """float: number of seconds to :func:`gevent.sleep` in our 
    :func:`~gevent_tasks.manager.TaskManager.forever` block between 
    looking for failed tasks.
    """

    def __init__(self, pool=None, logger=None):
        """ Interface for managing tasks and running them in a Gevent Pool.

        Args:
            pool (:class:`gevent.pool.Pool`): the concurrency pool that all
                of our underlying periodic tasks will run in. This is
                important to remember since our pool can only process
                its defined size of threads at one time. Tasks that block
                waiting for space in the pool may lapse their rerun period
                and fall into an undefined state.

                The recommended pool to use is
                :obj:`gevent_tasks.tasks.TaskPool` which has helper methods
                with information about the current run state of its
                greenlets_.

            logger (:obj:`logging.Logger`): logging instance from the
                standard library. If one isn't provided a new one will be
                made for this instance.

        .. _greenlets: http://www.gevent.org/gevent.html#greenlet-objects
        """
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

        or with keyword arguments that match those used for
        :obj:`.Task`, ::

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
            Callable of the underlying function.
        """
        def make_task(f, **kw):
            name = kw.get('name', _convert_fn_name(f.__name__))
            logger = kw.get('logger', None)
            if logger is None:
                logger = getLogger(self.logger.name + '.Task.%s' % name)
            kw.update({
                'fn': f,
                'name': name,
                'manager': self,
                'timeout': kw.get('timeout', 59.0),
                'interval': kw.get('interval', 60.0),
                'logger': logger
            })
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
        """:obj:`.TaskPool`: Reference to the underlying TaskPool instance."""
        return self._pool

    @property
    def task_names(self):
        """list(str): Copy of a list of all the registered task's names."""
        return [t for t in self._tasks.keys()]

    def get(self, name):
        """ Get a reference for a Task by its name.

        Returns:
            :obj:`.Task` when ``name`` is registered, ``None`` otherwise.
        """
        return self._tasks.get(name, None)

    def add(self, task, start=False):
        # type: (Task, bool) -> Task
        """ Add a task to the manager and optionally start executing it.

        Args:
            task (:obj:`.Task`): instance of Task to track in our manager.
            start (bool): if the task is not in a running state, should
                it be started.

        Raises:
            KeyError: when the Task's name is the same as one already being
                tracked.

        Returns:
            ``task``
        """
        if task.name in self._tasks:
            raise KeyError(task.name)
        if task.pool is None:
            task.pool = self._pool
        self._tasks[task.name] = task
        if start and not task.running:
            task.start()
        return task

    def add_many(self, *tasks, start=False):
        # type: (*Task, bool) -> None
        """ Add many tasks to the manager.

        Args:
            *tasks (:obj:`.Task`): variable amount of Tasks to track.
            start (bool): checks if each task has been started, if it
                hasn't when ``True`` the task will start.

        Raises:
            KeyError: when one of the Task's name is the same as one
                already being tracked.

        Returns:
            None
        """
        for task in tasks:
            self.add(task, start=start)

    def start(self, task_name):
        # type: (str) -> None
        """ Starts a registered Task by name.

        Args:
             task_name (str): will start a task by name if it's currently
                being tracked in the manager.

        Returns:
            None

        Raises:
            Nothing: will "fail" silently if a non-tracked name is given.
        """
        t = self._tasks.get(task_name, None)
        if t:
            t.start()

    def start_all(self):
        # type: () -> None
        """ Calls :func:`~start` on each Task being tracked.

        Returns:
            None
        """
        for task in self.task_names:
            self.start(task)

    def stop(self, task_name, force=False):
        """ Stop a registered task by name.

        Args:
            task_name (str): will stop a task by name if it's currently
                being tracked in the manager and running.
            force (bool): block the pool and event loop until this task
                can be forcibly terminated.

        Returns:
            None

        Raises:
            Nothing: will "fail" silently if a non-tracked name is given.
        """
        t = self._tasks.get(task_name, None)
        if t:
            t.stop(force)

    def stop_all(self, force=False):
        """ Calls :func:`~stop` on each Task being tracked.

        Args:
            force (bool): block the pool and event loop until each task
                can be forcibly terminated.

        Returns:
            None
         """
        for task in self.task_names:
            self.stop(task, force)

    def remove_task(self, task, force=False):
        """ Unregister a task from the manager by name or instance.

        Args:
            task (str or :obj:`.Task`): reference to a tracked Task.
            force (bool): calls :func:`.stop` with ``force`` before
                removing the Task from our manager.

        Returns:
            :obj:`Task` or ``None``
        """
        if hasattr(task, 'name'):
            name = task.name
        else:
            name = task
        t = self._tasks.pop(name, None)
        if t:
            t.stop(force)
        return t

    def remove_all(self, force=True):
        """ Calls :func:`.remove_task` for each Task being tracked.

        Args:
            force (bool): calls :func:`.stop` with ``force`` before
                removing the Task from our manager.

        Yields:
            :obj:`.Task`: each Task as it's removed. Allows for accessing
                additional runtime information before being garbage
                collected.
        """
        for task in self.task_names:
            yield self.remove_task(task, force)

    def forever(self, *exceptions, stop_after_exc=True, stop_on_zero=True):
        # type: (*Exception) -> bool
        """ Blocks in an infinite loop after starting all registered tasks.

        The only way to break out is if one of the included ``exceptions``
        is raised while being executed in a running task.

        Note:
            The loop will sleep for :attr:`.FOREVER_POOL_SECS` between
            checking Tasks for a failed state.

        Args:
            *exceptions (Exception): variable number of Exception classes
                to raise if an error occurs in a Task. This will break the
                Forever loop and effectively stop our TaskPool.

                Note:
                    :exc:`KeyboardInterrupt` is exempt from ``exceptions``
                    and will fail "gracefully" instead of re-raising to
                    break the loop.

            stop_after_exc (bool): stop the loop after our first exception.
            stop_on_zero (bool): stop the loop if no tasks are running.

        Returns:
            bool: ``True`` if everything stopped gracefully,
                otherwise ``False``.
         """
        e = None
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
        finally:
            return e is None
