from __future__ import print_function

import io
import os.path
import re
from distutils.text_file import TextFile

from setuptools import find_packages, setup

from tunicorn import __version__

home = os.path.abspath(os.path.dirname(__file__))
missing = object()


def read_description(*files, **kwargs):
    encoding = kwargs.get('encoding', 'utf-8')
    sep = kwargs.get('sep', '\n')
    buf = [io.open(name, encoding=encoding).read() for name in files]
    return sep.join(buf)


def read_dependencies(requirements=missing):
    if requirements is None:
        return []
    if requirements is missing:
        requirements = 'requirements.txt'
    if not os.path.isfile(requirements):
        return []
    text = TextFile(requirements, lstrip_ws=True)
    try:
        return text.readlines()
    finally:
        text.close()


def read_version(version_file):
    with open(version_file, 'rb') as fd:
        result = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]',
                           fd.read().decode(), re.MULTILINE)
        return result.group(1) if result else '0.0.1'


setup(
    name='Flask-NegLog',
    version=__version__,

    description='Socket HTTP Server for Unix',
    long_description=read_description('README.md'),

    url="https://github.com/by46/tunicorn",
    license='The MIT License',
    author='benjamin.c.yan',
    author_email='benjamin.c.yan@newegg.com',
    install_requires=read_dependencies(),
    include_package_data=True,
    packages=find_packages(),
    classifiers=[
        'Programming Language :: Python',
        'Development Status :: 3 - Alpha',
        'Natural Language :: English',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX',
        'Topic :: Software Development',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Software Distribution',
        'Topic :: Internet',
        'Topic :: Utilities',
        'Topic :: Internet :: WWW/HTTP'
    ]
)
