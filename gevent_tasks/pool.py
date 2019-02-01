#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# >>
#   gevent-tasks, 2018
# <<

from gevent import Greenlet
from gevent.pool import Pool

__all__ = ["TaskPool"]


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
                concurrent tasks that can be run at the same time. When
                ``size`` is None there is no hard-limit for the number
                of greenlets that can run at once.
        """
        if size is not None:
            size = max(2, size)
        super(TaskPool, self).__init__(size, Greenlet)

    def __repr__(self):
        return "<TaskPool(size=%d, running=%d, capacity=%0.1f%%)>" % (self.size, self.running,
                                                                      self.capacity)

    @property
    def running(self):
        """int: The number of currently running tasks in our pool."""
        return self.size - self.free_count()

    @property
    def capacity(self):
        """float: The current capacity of pool; how full as a percentage."""
        return (1 - (self.free_count() / float(self.size))) * 100
