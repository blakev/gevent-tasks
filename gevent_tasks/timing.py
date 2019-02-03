#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# >>
#   gevent-tasks, 2018
# <<

import time
import random
from math import ceil
from array import array


class ArrayDeque:

    """Light deque using a typed array with floats."""

    __slots__ = ("_col", "_len")

    def __init__(self, maxlen, type_code='f'):
        self._len = max(2, maxlen)
        self._col = array(type_code)

    def __getitem__(self, item):
        return self._col[item]

    def __iter__(self):
        yield from self._col

    def __len__(self):
        return len(self._col)

    @property
    def size(self):
        """int: returns the max length of the underlying array."""
        return self._len

    def append(self, o):
        if len(self) == self._len:
            # simple randomization for more structured averages
            self._col.pop(random.randint(1, int(ceil(self._len / 4.0))))
        self._col.append(o)


class Timing(object):

    """Base timing object to track per-Task statistics."""

    __slots__ = ("name", "_first_start", "_run_times", "_started", '_counter', '_total_time')

    MAX_RUN_TIMES = 1024
    "int: keep this many run times to compute averages."

    def __init__(self, task_name=None):
        """Instance inside of Task object tracks running times of that task.

        Args:
            task_name (str, optional): this is filled in automatically when
                an instance is created inside of a :obj:`.Task`.
        """
        self._counter = 0
        self._started = 0.0
        self._total_time = 0.0
        self._first_start = 0.0
        self._run_times = ArrayDeque(Timing.MAX_RUN_TIMES)
        self.name = task_name or ""

    def __iter__(self):
        yield from self.run_timings

    def __repr__(self):
        return "<Timing(count=%d, started=%0.2f, total=%0.3fs, last=%0.3fs)>" % (
            self.count, self.started, self.total, self.last)

    def as_dict(self, include_raw=True):
        """Return the timing information as a dictionary.

        Args:
            include_raw (bool): include a copy of the raw timings along side
                the summary values.

        Returns:
            dict
        """
        if include_raw:
            resp = {'raw': list(self)}
        else:
            resp = {'last': self.last}
        resp.update({
            'start': self.started,
            'first_started': self.first_started,
            'count': self.count,
            'average_time': self.average,
            'total_time': self.total,
            'best_time': self.best,
            'worst_time': self.worst
        })
        return resp

    def log(self, timing):
        """Mark a new finished time for the current task.

        Args:
            timing (float): recorded time in seconds.

        Returns:
            None
        """
        self._run_times.append(timing)
        self._total_time += timing

    def start(self):
        """Mark a new start time for the current task.

        Returns:
            None
        """
        if not self._first_start:
            self._first_start = time.time()
        self._started = time.monotonic()
        self._counter += 1

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
        """List[float]: read-only access to the log of recorded run timings."""
        return self._run_times if self._run_times else [-1.0]

    @property
    def average(self):
        """float: Total runtime divided by the successful runs count. """
        return self.total / max(1, self.count) if self.count > 0 else 0.0

    @property
    def count(self):
        """int: Total successful runs of a given task. """
        return self._counter

    @property
    def last(self):
        """float: Runtime of the last task call. """
        return self.run_timings[-1]

    @property
    def total(self):
        """float: Total runtime, so far, of all task runs. """
        return self._total_time

    @property
    def best(self):
        """float: Shortest single runtime for the task. """
        return min(self.run_timings)

    @property
    def worst(self):
        """float: Longest single runtime for the task. """
        return max(self.run_timings)
