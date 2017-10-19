# gevent-tasks

[![pypi](https://img.shields.io/pypi/v/gevent-tasks.svg?style=flat)](https://pypi.python.org/pypi/gevent-tasks)
[![docs](https://readthedocs.org/projects/gevent-tasks/badge/?version=latest)](http://gevent-tasks.readthedocs.io/en/latest/)
[![MIT License](https://img.shields.io/github/license/blakev/gevent-tasks.svg?style=flat)](https://github.com/blakev/gevent-tasks/blob/master/LICENSE)


Background task manager using Gevent and Green threads.

- Check out [the documentation](http://gevent-tasks.readthedocs.io/en/latest/).
- Learn about [Gevent]().

This library is designed to allow a developer to run arbitrary "tasks" as background
threads on a fixed/normalized interval.  Each task is a wrapped
callable that takes at least one parameter `task`, a reference to itself. Timings
and related metadata can be accessed via the `task` value as well as the ability
to stop and reschedule itself for future events.


`TaskManager` has a `TaskPool` that runs `Tasks`.

## Installation

The latest version from pypi,

```bash
$ pip install gevent-tasks
```

The latest development version from source,

```bash
$ pip install git+git@github.com:blakev/gevent-tasks.git@develop
```



## Examples

A classic example,

```python
# print our system uptime every minute, indefinitely

from datetime import timedelta
from gevent_tasks import TaskManager, cron

manage = TaskManager()

@manage.task(interval=cron('* * * * *'))
def system_uptime(task):
    with open('/proc/uptime', 'r') as f:
        uptime_seconds = float(f.readline().split()[0])
        uptime = str(timedelta(seconds=uptime_seconds))
    print(uptime)

manage.forever(stop_after_exc=False)
```

Contrived example,

```python
from gevent.monkey import patch_all
patch_all()

from gevent_tasks import Task, TaskManager, TaskPool

from myapp.tasks import check_websockets, check_uptime, check_health

pool = TaskPool(size=25)
manager = TaskManager(pool=pool)

manager.add_many(
    Task('WebsocketHealth', check_websockets, interval=7.5),
    Task('ApplicationHealth', check_uptime, interval=30.0),
    Task('SystemHealth', check_health, args=('localhost',), interval=2.5)
)
manager.start_all()
..
..
http_server.serve_forever()
```

Using the [`parse-crontab`](https://github.com/josiahcarlson/parse-crontab)
 module we're able to define intervals with cron syntax,

```python
from gevent_tasks import Task, cron
..
..
Task('ShowCharts', show_charts, interval=cron('* * * * *'), timeout=30.0)
```

The manager instance can also be used to register tasks via decorator. Calling 
`TaskManager.forever()` will block the code until there are no longer scheduled tasks or until an `Exception` 
is thrown inside one of the running Tasks.

```python
manage = TaskManager()

@manage.task(interval=cron('* * * * *'))
def every_minute(task, *args):
    print('hi', args, task, task.timing)

manage.forever()
```

You can also reference the previous return value, allowing tasks to build on
themselves over time without human / programmatic interaction.

```python
@manage.task(interval=1)
def random_number(task):
    num = random.randint(0, 100)
    print(task.value, num)
    return num

.. output ..

None 51
51 50
50 88
88 26
```

### Attribution

This module relies primarily on the [`gevent`](http://www.gevent.org/index.html) 
project for all its core functionality.

### MIT License

Copyright (c) 2017 Blake VandeMerwe

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
