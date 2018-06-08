#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# >>
#   Copyright 2018 Vivint, inc.
#
#   gevent-tasks, 2018
# <<

import time


class Timing(object):
    __slots__ = ("name", "_first_start", "_run_times", "_started")

    def __init__(self, task_name=None):
        """Instance inside of Task object tracks running times of that task.

        Args:
            task_name (str, optional): this is filled in automatically when
                an instance is created inside of a :obj:`.Task`.

        """
        self._first_start = 0  # type: float
        self._started = 0  # type: float
        self._run_times = []  # type: List[float]
        self.name = task_name or ""

    def __iter__(self):
        yield from self.history()

    def __repr__(self):
        return "<Timing(%scount=%d,started=%0.2f,last=%0.4f)>" % (
            ("name=%s," % self.name)
            if self.name else "", self.count, self.started, self.last)

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
        for timing in self.run_timings:
            yield timing

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
