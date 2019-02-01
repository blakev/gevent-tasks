#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# >>
#   gevent-tasks, 2019
# <<


class GeventTasksError(Exception):

    """Base exception class."""


class TaskKeyError(GeventTasksError, KeyError):

    """Thrown inside task execution when namespacing has an issue."""


class TaskRuntimeError(GeventTasksError, RuntimeError):

    """Thrown inside task execution when something goes wrong."""


class ForeverRuntimeError(GeventTasksError, RuntimeError):

    """Thrown from :func:`gevent_tasks.manager.TaskManager.forever`."""
