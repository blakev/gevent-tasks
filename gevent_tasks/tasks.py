#! /usr/bin/env python
# -*- coding: utf-8 -*-
# >>
#     gevent-tasks, 2017
# <<

import time
from numbers import Real
from functools import wraps
from logging import getLogger

import gevent
from gevent import Greenlet, Timeout
from gevent.pool import Pool


class TaskPool(Pool):
    """ Custom gevent thread pool for reporting capacity statistics. """

    def __init__(self, size=None):
        # type: (int) -> self
        if size is not None:
            size = max(2, size)
        super(TaskPool, self).__init__(size, Greenlet)

    @property
    def running(self):
        # type: () -> int
        return self.size - self.free_count()

    @property
    def capacity(self):
        # type: () -> float
        return (1 - (self.free_count() / float(self.size))) * 100


class Timing(object):
    def __init__(self):
        self._started = 0
        self._run_times = []

    def log(self, timing):
        self._run_times.append(timing)

    def start(self):
        self._started = time.time()

    def history(self):
        for o in self._run_times:
            yield o

    @property
    def started(self):
        return self._started

    @property
    def run_timings(self):
        if not self._run_times:
            return [-1]
        return self._run_times

    @property
    def average(self):
        return self.total / max(1, self.count)

    @property
    def count(self):
        return len(self.run_timings)

    @property
    def last(self):
        return self.run_timings[-1]

    @property
    def total(self):
        return sum(self.run_timings)

    @property
    def best(self):
        return min(self.run_timings)

    @property
    def worst(self):
        return max(self.run_timings)


class Task(object):
    def __init__(self, name, fn, args=None, kwargs=None, timeout=None,
                 interval=None, description=None, logger=None, pool=None):

        if timeout is None:
            timeout = -1

        if args is None:
            args = tuple()

        if kwargs is None:
            kwargs = {}

        self.name = name                # type: str
        self.description = description  # type: str
        self.logger = logger or getLogger('%s.Task.%s' % (__name__, self.name))

        self._fn = fn                   # type: Callable
        self._fn_arg = args             # type: tuple
        self._fn_kw = kwargs            # type: dict
        self._g = None                  # type: Greenlet
        self._running = False           # type: bool
        self._schedule = False          # type: bool
        self._timeout_secs = timeout    # type: float
        self._timeout_obj = None        # type: Timeout
        self._interval = interval       # type: float
        self.timing = Timing()          # type: Timing
        self.pool = pool                # type: TaskPool

    def __repr__(self):
        return '<Task(name=%s)>' % self.name

    def __make(self):
        g = Greenlet(self._fn, self, *self._fn_arg, **self._fn_kw)
        g.link(self.__callback)
        return g

    def __callback(self, *args):
        duration = time.time() - self.timing.started
        if self._timeout_secs and self._timeout_obj:
            self._timeout_obj.cancel()
        self._g = None
        self._running = False
        self.timing.log(duration)
        if self.is_periodic and self._schedule:
            gevent.spawn_later(
                max(0, self._interval - duration), self.start)

    def start(self):
        if self.is_running:
            self.logger.warning('task is already running')
        elif self._g:
            self.logger.error('task is already claimed greenlet')
        else:
            self._schedule = True

        if not self._schedule:
            return

        if self._timeout_obj:
            self._timeout_obj.cancel()
            self._timeout_obj = None
        if self._timeout_secs > 0:
            self._timeout_obj = Timeout(
                self._timeout_secs, exception=TimeoutError)
            self._timeout_obj.start()

        self.timing.start()

        try:
            self._g = self.__make()
            self.pool.start(self._g)
            self._running = True

        except TimeoutError as e:
            self.logger.warning(e)
            self.__callback()

        except Exception as e:
            self.logger.exception(e, exc_info=True)
            raise e

    def stop(self, force=False):
        if self.is_running and self._g is not None:
            self._g.unlink(self.__callback)
            if force:
                self._g.kill(block=True, timeout=self._timeout_secs)
        self._schedule = False
        self.__callback()

    @property
    def is_running(self):
        if self._interval:
            return self.timing.started + self._interval > time.time()
        return self._running  # guess

    @property
    def is_periodic(self):
        return isinstance(self._interval, Real)



