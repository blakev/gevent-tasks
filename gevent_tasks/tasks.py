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
from crontab import CronTab
from gevent import Greenlet, Timeout
from gevent.pool import Pool

from gevent_tasks.utils import gen_uuid

__all__ = [
    'Task',
    'TaskPool',
    'Timing',
    'cron'
]


class TaskPool(Pool):

    DEFAULT_POOL_SIZE = 10
    """int: size of underlying :class:`gevent.pool.Pool`. 
    
    This value is used when the :obj:`~gevent_tasks.TaskManager` has an 
    ambiguous pool defined when it's instantiated.
    """

    def __init__(self, size=None):
        """Custom gevent thread pool for reporting capacity statistics.

        Args:
            size (int, optional): thread pool size, maximum number of
                concurrent tasks that can be run at the same time.

        """
        if size is not None:
            size = max(2, size)
        super(TaskPool, self).__init__(size, Greenlet)

    def __repr__(self):
        return '<TaskPool(size=%d,running=%d,capacity=%0.1f%%)>' % (
            self.size, self.running, self.capacity)

    @property
    def running(self):
        """int: The number of currently running tasks in our pool."""
        return self.size - self.free_count()

    @property
    def capacity(self):
        # type: () -> float
        """float: The current run capacity of our pool; how full as
        a percentage.
        """
        return (1 - (self.free_count() / float(self.size))) * 100


class Timing(object):

    __slots__ = ('_first_start', '_run_times', '_started', 'name')

    def __init__(self, task_name=None):
        """ Instance inside of Task object tracks running times of that task.

        Args:
            task_name (str, optional): this is filled in automatically when
                an instance is created inside of a :obj:`.Task`.

        """
        # type: (str) -> self
        self._first_start = 0   # type: float
        self._started = 0       # type: float
        self._run_times = []    # type: List[float]
        self.name = task_name or ''

    def __iter__(self):
        return self.history()

    def __repr__(self):
        return '<Timing(%scount=%d,started=%0.2f,last=%0.4f)>' % (
            ('name=%s,' % self.name) if self.name else '',
            self.count, self.started, self.last)

    def log(self, timing):
        """Mark a new finished time for the current task.

        Args:
            timing (float): recorded time in seconds.

        Returns:
            None
        """
        self._run_times.append(timing)

    def start(self):
        """Mark a new start time for the current task.

        Returns:
            None
        """
        self._started = time.time()
        if self._first_start == 0:
            self._first_start = self._started

    def history(self):
        """Iterate over all the saved timings.

        Yields:
            float: the next timing recorded.
        """
        for o in self.run_timings:
            yield o

    @property
    def started(self):
        """float: Unix timestamp of the last/currently running task started."""
        return self._started

    @property
    def first_started(self):
        """float: Unix timestamp of the first run of the task started. """
        return self._first_start

    @property
    def run_timings(self):
        """:obj:`list` of obj:`floats`: read-only access to the log of recorded
        run timings.
        """
        if not self._run_times:
            return [0]
        return self._run_times

    @property
    def average(self):
        """float: Total runtime divided by the successful runs count. """
        return self.total / max(1, self.count)

    @property
    def count(self):
        """int: Total successful runs of a given task. """
        return len(self.run_timings)

    @property
    def last(self):
        """float: Runtime of the last task call. """
        return self.run_timings[-1]

    @property
    def total(self):
        """float: Total runtime, so far, of all task runs. """
        return sum(self.run_timings)

    @property
    def best(self):
        """float: Shortest single runtime for the task. """
        return min(self.run_timings)

    @property
    def worst(self):
        """float: Longest single runtime for the task. """
        return max(self.run_timings)


class Task(object):
    def __init__(self, name, fn, args=None, kwargs=None,
                 timeout=None, interval=None, description=None, logger=None,
                 manager=None, pool=None):
        """ A Task represents a unit of work that can take place in the
            background of a gevent-based application.

            Args:
                name (str):
                fn (Callable):
                args (Tuple[Any]):
                kwargs (Dict[str, Any]):
                timeout (float):
                interval (Union[float, CronTab]):
                description (str):
                logger (Logger):
                manager (TaskManager):
                pool (TaskPool):
        """
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
        self._exc_info = None            # type: tuple
        self._last_value = None          # type: Any
        self._schedule = False           # type: bool
        self._timeout_secs = timeout     # type: float
        self._timeout_obj = None         # type: Timeout
        # ~~ back references
        self.pool = pool                 # type: TaskPool
        self.manager = manager           # type: TaskManager
        self.timing = Timing(self.name)  # type: Timing
        # ~~ delayed parsing
        self._interval = self.parse_interval(interval)

    def __repr__(self):
        return '<Task(name=%s,runs=%d,runtime=%0.2f)>' % (
            self.name, self.timing.count, self.timing.total)

    def __make(self):
        # type: () -> Greenlet
        g = Greenlet(self._fn, self, *self._fn_arg, **self._fn_kw)
        g.link_value(self.__callback)
        g.link_exception(self.__err_callback)
        return g

    def __callback(self, *args):
        g = args[0] if args else None
        if g is not None and hasattr(g, 'value'):
            self._last_value = g.value
        duration = time.time() - self.timing.started
        if self._timeout_secs and self._timeout_obj and \
                self._timeout_obj.pending:
            self.logger.debug('canceling timeout')
            self._timeout_obj.cancel()
        self._g = None
        self._running = False
        self.timing.log(duration)
        if self.is_periodic and self._schedule:
            if isinstance(self._interval, CronTab):
                when = self._interval.next()
            else:
                when = max(0, self._interval - duration)
            gevent.spawn_later(when, self.start)
            self.logger.debug('scheduled to run in %0.2f', when)

    def __err_callback(self, g):
        self._running = None
        self._exc_info = g.exc_info
        self.logger.error('raised an exception')

    @property
    def value(self):
        # type: () -> Any
        """ Stores the previous run's value. """
        return self._last_value

    @classmethod
    def parse_interval(cls, i):
        """ Turns an interval into a usable time tracking value.

            Args:
                i (Any): converts ``i`` into seconds if it's numeric,
                    otherwise attempts to convert to a CronTab instance
                    for per-minute granularity.

            Returns:
                float: when ``i`` is numeric-like.
                CronTab: when ``i`` is string or cron-like.

            Raises:
                ValueError: when a determination cannot be made.
        """
        if i is None or not i:
            # no interval
            return None
        elif isinstance(i, Real):
            # seconds interval
            return float(i)
        elif isinstance(i, str):
            # coerce to CronTab
            return CronTab(i)
        elif isinstance(i, CronTab):
            return i
        else:
            raise ValueError('cannot use interval of type %s' % type(i))

    def fork(self, name=None):
        """ Fork the current task to create a duplicate running under
            the same TaskManager. This instance will also be tracked and
            receive the same checks as if it were registered initially.

            Args:
                name (str): ``name`` of the new Task.

            Raises:
                ValueError: when a required attribute is not set or is
                    missing.

            Returns:
                Task
        """
        if not self.manager:
            raise ValueError('cannot fork task without manager')

        if name is None:
            name = '%sFork-%s' % (self.name, gen_uuid())

        if name in self.manager.task_names:
            raise ValueError(
                'cannot create a task with duplicate name %s' % name)

        kwargs = dict(
            name=name,
            args=self._fn_arg,
            kwargs=self._fn_kw,
            timeout=self._timeout_secs,
            interval=self._interval,
            description=self.description,
            # generate a new logger with the new name
            logger=None
        )

        # build a partial, from a decorator, then re-call to build
        task_fn = self.manager.task(**kwargs)
        task_fn(self._fn)

        task = self.manager.get(name)

        if task is None:
            raise RuntimeError('could not add forked task to manager')

        task.start()

        return task

    def start(self):
        # type: () -> None
        """ Start the periodic task.

            Warning::
                Do not call this function directly. It should instead by
                called by a TaskManager instance or some other object that
                can keep track of running Tasks.

            Raises:
                TimeoutError: when a Task's runtime exceeds its per-run
                    limit for maximum execution time.
                Exception: for all other cases.

            Returns:
                None
        """
        if self.running:
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
        """ Stop the periodic task. """
        if self.running is None and self._exc_info is not None:
            self._g.kill(self._exc_info[1], block=False)
        if self.running and self._g is not None:
            self._g.unlink(self.__callback)
            if force:
                self._g.kill(block=True, timeout=self._timeout_secs)
        self._schedule = False
        self.__callback()

    @property
    def running(self):
        # type: () -> bool
        """ Determines if the current task is running or stopped. """
        if not self._g:
            return False
        if self._g.dead or self._g.exception is not None:
            return False
        return any([self._g.started, self._running])

    @property
    def is_periodic(self):
        # type: () -> bool
        """ Determines if interval has been set, otherwise a one-off task. """
        return isinstance(self._interval, (CronTab, Real))


# alias
cron = CronTab
