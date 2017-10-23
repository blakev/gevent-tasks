#! /usr/bin/env python
# -*- coding: utf-8 -*-
# >>
#   gevent-tasks, 2017
#
#       Background task management using gevent green threads.
#
#   Blake VandeMerwe
#   blakev@null.net
# <<

import os
import re
import sys
from os.path import dirname, join as pjoin
from setuptools import setup, find_packages, Command
from setuptools.command.test import test as TestCommand

ATTRIBUTES = re.compile(r"^__(\w+)__\s+=\s+'(.*?)'$", re.S + re.M)

dname = dirname(__file__)

with open(pjoin(dname, 'gevent_tasks', '__init__.py')) as ins_file:
    text = ins_file.read()
    attrs = ATTRIBUTES.findall(text)
    A = dict(attrs)

with open(pjoin(dname, 'requirements.txt')) as ins_file:
    requirements = map(str.strip, ins_file.readlines())


class RunTests(TestCommand):
    """
    Run the unit tests.
    By default, `python setup.py test` fails if tests/ isn't a Python
    module (that is, if the tests/ directory doesn't contain an
    __init__.py file). But the tests/ directory shouldn't contain an
    __init__.py file and tests/ shouldn't be a Python module. See
      http://doc.pytest.org/en/latest/goodpractices.html
    Running the unit tests manually here enables `python setup.py test`
    without tests/ being a Python module.
    """
    def run_tests(self):
        from unittest import TestLoader, TextTestRunner
        tests_dir = pjoin(dirname(__file__), 'tests')
        suite = TestLoader().discover(tests_dir)
        result = TextTestRunner().run(suite)
        sys.exit(0 if result.wasSuccessful() else -1)


long_description = (
    'Information and documentation found can be found'
    ' at https://github.com/blakev/gevent-tasks.')


setup(
    name='gevent-tasks',
    version=A['version'],
    author=A['author'],
    author_email=A['contact'],
    url=A['url'],
    license=A['license'],
    documentation='http://gevent-tasks.readthedocs.io/en/latest/',
    description='Background task management using gevent and green threads.',
    long_description=long_description,
    packages=find_packages(),
    include_package_data=True,
    platforms=['any'],
    install_requires=list(requirements),
    cmdclass={
        'test': RunTests
    },
    classifiers=[
        'Topic :: Software Development :: Libraries',
        'Natural Language :: English',
        'License :: OSI Approved :: MIT License',
        'Intended Audience :: Developers',
        'Development Status :: 4 - Beta',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6'
    ]
)
