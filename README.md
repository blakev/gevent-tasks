# gevent-tasks

[![pypi](https://img.shields.io/pypi/v/gevent-tasks.svg?style=flat)](https://pypi.python.org/pypi/gevent-tasks)
[![MIT License](https://img.shields.io/github/license/blakev/gevent-tasks.svg?style=flat)](https://github.com/blakev/gevent-tasks/blob/master/LICENSE)


Task manager built around the gevent green threads library.

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



```python
from gevent.monkey import patch_all
patch_all()

from gevent import sleep
from gevent_tasks import Task, TaskManager, TaskPool

def print_hi(task, *args):
    print('hi', args, task, task.timing)

manager = TaskManager(TaskPool(size=3))
manager.add_many(
    Task('PrintHi', print_hi, interval=1.5),
    Task('PrintHiArgs', print_hi, args=(1, 2, 3,), interval=3.0)
)
manager.start_all()

while True:
    sleep(0.25)
```

Using the [`parse-crontab`](https://github.com/josiahcarlson/parse-crontab)
 module we're able to define intervals with cron syntax,

```python
from gevent_tasks import Task, cron
...
...
Task('PrintHi', print_hi, interval=cron('* * * * *'))
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
