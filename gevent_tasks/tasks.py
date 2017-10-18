#! /usr/bin/env python
# -*- coding: utf-8 -*-
# >>
#     gevent-tasks, 2017
# <<

import time
from typing import List, Generator
from numbers import Real
from logging import getLogger

import gevent
from gevent import Greenlet, Timeout
from gevent.pool import Pool


class TaskPool(Pool):
    """ Custom gevent thread pool for reporting capacity statistics. """

    DEFAULT_POOL_SIZE = 10

    def __init__(self, size=None):
        # type: (int) -> self
        if size is not None:
            size = max(2, size)
        super(TaskPool, self).__init__(size, Greenlet)

    def __repr__(self):
        return '<TaskPool(size=%d,running=%d,capacity=%0.1f%%)>' % (
            self.size, self.running, self.capacity)

    @property
    def running(self):
        # type: () -> int
        """ The number of currently running tasks in our pool. """
        return self.size - self.free_count()

    @property
    def capacity(self):
        # type: () -> float
        """ The current run capacity of our pool; how full as a percentage. """
        return (1 - (self.free_count() / float(self.size))) * 100


class Timing(object):
    """ Instance inside of Task object tracks running times of that task. """

    __slots__ = ('_first_start', '_run_times', '_started', 'name')

    def __init__(self, task_name=None):
        # type: (str) -> self
        self._first_start = 0   # type: float
        self._started = 0       # type: float
        self._run_times = []    # type: List[float]
        self.name = task_name or ''

    def __iter__(self):
        return self.history()

    def __repr__(self):
        return '<Timing(%scount=%d,started=%0.2f,last=%0.4f)>' % (
            ('name=%s,' % self.name) if self.name else '', self.count,
            self._first_start, self.last)

    def log(self, timing):
        # type: (float) -> None
        """ Mark a new finished time for the current task. """
        self._run_times.append(timing)

    def start(self):
        # type: () -> None
        """ Mark a new start time for the current task. """
        self._started = time.time()
        if self._first_start == 0:
            self._first_start = self._started

    def history(self):
        # type: () -> Generator[float]
        """ Iterator over all the saved timings. """
        for o in self.run_timings:
            yield o

    @property
    def started(self):
        # type: () -> float
        """ Unix timestamp of the last/currently running task started. """
        return self._started

    @property
    def first_started(self):
        # type: () -> float
        """ Unix timestamp of the first run of the task started. """
        return self._first_start

    @property
    def run_timings(self):
        # type: () -> List[float]
        """ Read-only getting for the collection of run timings.  """
        if not self._run_times:
            return [-1]
        return self._run_times

    @property
    def average(self):
        """ Total runtime divided by the successful runs count. """
        # type: () -> float
        return self.total / max(1, self.count)

    @property
    def count(self):
        """ Total successful runs of a given task. """
        # type: () -> int
        return len(self.run_timings)

    @property
    def last(self):
        # type: () -> float
        """ Runtime of the last task call. """
        return self.run_timings[-1]

    @property
    def total(self):
        # type: () -> float
        """ Total runtime, so far, of all task runs. """
        return sum(self.run_timings)

    @property
    def best(self):
        # type: () -> float
        """ Shortest single runtime for the task. """
        return min(self.run_timings)

    @property
    def worst(self):
        # type: () -> float
        """ Longest single runtime for the task. """
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
        # ~~
        self._fn = fn                    # type: Callable
        self._fn_arg = args              # type: tuple
        self._fn_kw = kwargs             # type: dict
        self._g = None                   # type: Greenlet
        self._running = False            # type: bool
        self._schedule = False           # type: bool
        self._timeout_secs = timeout     # type: float
        self._timeout_obj = None         # type: Timeout
        self._interval = interval        # type: float
        self.timing = Timing(self.name)  # type: Timing
        self.pool = pool                 # type: TaskPool

    def __repr__(self):
        return '<Task(name=%s)>' % self.name

    def __make(self):
        # type: () -> Greenlet
        g = Greenlet(self._fn, self, *self._fn_arg, **self._fn_kw)
        g.link(self.__callback)
        return g

    def __callback(self, *args):
        duration = time.time() - self.timing.started
        if self._timeout_secs and self._timeout_obj and \
                self._timeout_obj.pending:
            self.logger.debug('canceling timeout')
            self._timeout_obj.cancel()
        self._g = None
        self._running = False
        self.timing.log(duration)
        if self.is_periodic and self._schedule:
            when = max(0, self._interval - duration)
            gevent.spawn_later(when, self.start)
            self.logger.debug('scheduled to run in %0.2f', when)

    def start(self):
        # type: () -> None
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
            self._timeout_obj = Timeout.start_new(
                self._timeout_secs, TimeoutError)

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
        # type: (bool) -> None
        if self.is_running and self._g is not None:
            self._g.unlink(self.__callback)
            if force:
                self._g.kill(block=True, timeout=self._timeout_secs)
        self._schedule = False
        self.__callback()

    @property
    def is_running(self):
        # type: () -> bool
        if self._interval:
            return self.timing.started + self._interval > time.time()
        return self._running  # guess

    @property
    def is_periodic(self):
        # type: () -> bool
        return isinstance(self._interval, Real)



