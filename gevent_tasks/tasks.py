#! /usr/bin/env python
# -*- coding: utf-8 -*-
# >>
#     gevent-tasks, 2017
# <<

import time
from numbers import Real
from logging import getLogger
from datetime import timedelta

import gevent
from crontab import CronTab
from gevent import Greenlet, Timeout
from gevent.event import Event

from gevent_tasks.errors import TaskKeyError, TaskRuntimeError
from gevent_tasks.timing import Timing
from gevent_tasks.utils import gen_uuid

__all__ = ["Task", "NullTask"]


class Task(object):

    """Base Task implementation."""

    __slots__ = ("_event", "_exc_info", "_fn", "_fn_arg", "_fn_kw", "_g", "_interval",
                 "_last_value", "_no_self", "_running", "_schedule", "_timeout_obj",
                 "_timeout_secs", "description", "event", "logger", "manager", "name", "pool",
                 "timing")

    def __init__(self,
                 name,
                 fn,
                 args=None,
                 kwargs=None,
                 timeout=None,
                 interval=None,
                 description=None,
                 logger=None,
                 manager=None,
                 pool=None,
                 no_self=False,
                 greedy=False,
                 event=None):
        """A Task represents a unit of work, run on a fixed interval, that can take place in the
        background of a gevent-based application.

        Args:
            name (str): the name of the Task. Used for reference in a Manager,
                as well as generating logging instances.
            fn (Callable): the function wrapped by the Task instance.
            args (Tuple[Any]): arguments supplied to ``fn``.
            kwargs (Dict[str, Any]): keyword arguments supplied to ``fn``.
            timeout (float): raise :exc:`gevent.Timeout` if ``fn`` has been
                running longer than this amount. If no timeout is set the
                function can run indefinitely.
            interval (float or :obj:`.CronTab`): run ``fn`` every ``interval``
                seconds for as long as the application is running. An instance
                of :class:`crontab.CronTab` is also acceptable. When ``None``
                the task is considered a "one off" and will only run one time.
            description (str): meta-data description for a Task instance.
            logger (:obj:`logging.Logger`): instance of a standard library
                Logger.
            manager (:class:`~gevent_tasks.manager.TaskManager`): instance that
                will control and track our running task instance.
            pool (:class:`~gevent_tasks.pool.TaskPool`): filled in by
                ``manager`` when the Task is ``add``.
            no_self (bool): when ``True`` do NOT pass a self-reference to the
                :obj:`.Task` instance to the underlying function.
            greedy (bool): when ``True`` call ``fn`` immediately. This instance
                will not run in the task pool and its results/exception will
                not be tracked or handled.
            event (:class:`~gevent.event.Event`): check ``is_set()`` before performing
                the scheduled call. The underlying schedule will remain uninterrupted.
        """
        # yapf: disable
        if timeout is None:
            timeout = -1

        if args is None:
            args = tuple()

        if kwargs is None:
            kwargs = {}

        self.name = name                # type: str
        self.description = description  # type: str
        self.logger = logger or getLogger("%s.Task.%s" % (__name__, self.name))
        # ~~
        self._fn = fn                   # type: Callable
        self._fn_arg = args             # type: tuple
        self._fn_kw = kwargs            # type: dict
        self._g = None                  # type: Greenlet
        self._running = False           # type: bool
        self._exc_info = None           # type: tuple
        self._last_value = None         # type: Any
        self._no_self = no_self         # type: bool
        self._schedule = False          # type: bool
        self._timeout_secs = timeout    # type: float
        self._timeout_obj = None        # type: Timeout
        self._event = event             # type: Event
        # ~~ back references
        self.pool = pool                 # type: TaskPool
        self.manager = manager           # type: TaskManager
        self.timing = Timing(self.name)  # type: Timing
        # ~~ delayed parsing
        self._interval = self.parse_interval(interval)

        if self._event is None:
            self._event = Event()
            self._event.set()

        if greedy and self._event.is_set():
            self.logger.debug("performing greedy run")
            g = self.__make(is_greedy=True)
            g.start()
        # yapf: enable

    def __repr__(self):
        return "<Task(name=%s, runs=%d, runtime=%0.2f)>" % (self.name, self.timing.count,
                                                            self.timing.total)

    def __make(self, is_greedy=False):
        # type: (bool) -> Greenlet
        if self._no_self:
            g = Greenlet(self._fn, *self._fn_arg, **self._fn_kw)
        else:
            g = Greenlet(self._fn, self, *self._fn_arg, **self._fn_kw)
        if not is_greedy:
            # normal scenario
            g.link_value(self.__callback)
            g.link_exception(self.__err_callback)
        return g

    def __callback(self, g, stats_only=False):
        # type: (Greenlet, bool) -> None
        if g and hasattr(g, "value"):
            self._last_value = g.value
        duration = time.monotonic() - self.timing.started
        if self._timeout_secs and self._timeout_obj and self._timeout_obj.pending:
            self.logger.debug("canceling timeout")
            self._timeout_obj.cancel()
        if stats_only:
            return
        # reset the Greenlet
        self._g = None
        self._running = False
        self.timing.log(duration)
        if self.is_oneoff:
            self.logger.debug("will not schedule task to re-run")
        elif self.is_periodic and self._schedule:
            if isinstance(self._interval, CronTab):
                when = self._interval.next(default_utc=True)
            else:
                when = max(0, self._interval - duration)
            gevent.spawn_later(when, self.start)
            self.logger.debug("scheduled to run in %0.2f", when)

    def __err_callback(self, g):
        # type: (Greenlet) -> None
        self._running = None
        self._exc_info = g.exc_info
        self.logger.error("raised an exception")

    @property
    def ident(self):
        """int: A small, unique integer that identifies this greenlet."""
        if self._g:
            return self._g.minimal_ident
        return None

    id = ident  # alias

    @property
    def value(self):
        """Any: Stores the previous run's value."""
        return self._last_value

    @property
    def exception_info(self):
        """tuple: Stores the previous run's exception, if one was thrown."""
        return self._exc_info

    @classmethod
    def parse_interval(cls, i):
        """Turns an interval into a usable time tracking value.

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
        elif isinstance(i, timedelta):
            # seconds interval
            return i.total_seconds()
        elif isinstance(i, Real):
            # seconds interval
            return float(i)
        elif isinstance(i, str):
            # coerce to CronTab
            return CronTab(i)
        elif isinstance(i, CronTab):
            return i
        else:
            raise TaskRuntimeError("cannot use interval of type %s" % type(i))

    def fork(self, name=None):
        """Fork the current task to create a duplicate running under the same TaskManager. This
        instance will also be tracked and receive the same checks as if it were registered
        initially.

        Args:
            name (str): ``name`` of the new Task.

        Raises:
            ValueError: when a required attribute is not set or is
                missing.

        Returns:
            Task
        """
        if not self.manager:
            raise TaskRuntimeError("cannot fork task without manager")

        if name is None:
            name = "%sFork-%s" % (self.name, gen_uuid())

        if name in self.manager.task_names:
            raise TaskKeyError("cannot create a task with duplicate name %s" % name)

        kwargs = dict(
            name=name,
            args=self._fn_arg,
            kwargs=self._fn_kw,
            timeout=self._timeout_secs,
            interval=self._interval,
            description=self.description,
            # generate a new logger with the new name
            logger=None)

        # build a partial Task with known kwargs
        task_fn = self.manager.task(**kwargs)
        # call the partial with underlying function to add to manager
        task_fn(self._fn)
        # ensure the task was added to the manager
        task = self.manager.get(name)
        if task is None:
            raise TaskRuntimeError("could not add forked task to manager")
        # start running the task, and return for inspection
        task.start()
        return task

    def start(self):
        """Start the periodic task.

        Warning:
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
            self.logger.warning("task is already running")
        elif self._g:
            self.logger.error("task has already claimed Greenlet")
        else:
            self._schedule = True
        # do not schedule this task to run
        if not self._schedule:
            self.logger.debug('task is not being scheduled to run')
            return

        if not self._event.is_set():
            self.logger.debug('skipping task run, event is not set')
            self.__callback(None)
            return

        # handle a potential timeout
        if self._timeout_obj:
            self._timeout_obj.cancel()
            self._timeout_obj = None
        if self._timeout_secs > 0:
            self._timeout_obj = Timeout.start_new(self._timeout_secs, TimeoutError)
        try:
            self._g = self.__make()
            self.timing.start()
            self.pool.start(self._g)
            self._running = True
        except TimeoutError as e:
            self.logger.warning(e)
            self.__callback(self._g)
        except Exception as e:
            self.logger.exception(e, exc_info=True)
            raise TaskRuntimeError from e

    def stop(self, force=False):
        """Stop the periodic task.

        Args:
             force (bool): block the pool and event loop until this task
                can be forcibly terminated.

        Returns:
            None

        Warnings:
            If the code executing is not exception safe (e.g., makes proper use of
            finally) then an unexpected exception could result in corrupted state.

            Because of Greenlet scheduling starting/stopping a task via the Manager may
            have unintended consequences. There is no guarantee of atomic task runs depending
            on the underlying scheduler and event loop.
        """
        self._schedule = False
        self._running = False
        if self._exc_info is not None:
            self._g.kill(self._exc_info[1], block=False)
        elif self.running and self._g is not None:
            self._g.unlink(self.__callback)
        self.__callback(self._g, stats_only=True)
        self._g.kill(block=True, timeout=self._timeout_secs)

    def abort(self):
        """Force stop and remove task from manager, cancels all future runs without manually
        re-adding the task."""
        self.manager.remove_task(self)
        self.stop(force=True)

    def done(self):
        """Signals that this task should not be rescheduled after its current run. This method
        should be called inside the Task's function body."""
        self.logger.debug('un-scheduling task from future iterations')
        self._schedule = False

    @property
    def running(self):
        """bool: if the current task is running or stopped."""
        if not self._g:
            return False
        if self._g.dead or self._g.exception is not None:
            return False
        return self._g.started or self._running

    @property
    def scheduled(self):
        """bool: the task is running or scheduled to run next iteration."""
        return self._schedule or self.running

    @property
    def is_periodic(self):
        """bool: if ``interval`` is set and also a valid type."""
        return isinstance(self._interval, (CronTab, Real))

    @property
    def is_oneoff(self):
        """bool: this task will only be run once then discarded."""
        return not self.is_periodic


class NullTask(Task):

    """Task class that produces zero-cost instances, useful for debugging.

    Returns:
        :obj:`.Task`: Task instance.
    """

    def __init__(self, **kwargs):
        kwargs.update(dict(description="DOES NOTHING", args=None, kwargs=None, no_self=True))
        super().__init__("NullTask", NullTask.null_fn, **kwargs)

    @staticmethod
    def null_fn():
        """NO OP null function for filler task."""
        return True
