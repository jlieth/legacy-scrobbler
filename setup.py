#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import setup, find_packages
import sys

assert sys.version_info >= (3, 6, 0), "Python 3.6+ is required"
from pathlib import Path  # noqa E402

CURRENT_DIR = Path(__file__).parent

with open(CURRENT_DIR / "requirements.txt", encoding="utf8") as f:
    REQUIREMENTS = f.readlines()

with open(CURRENT_DIR / "requirements_dev.txt", encoding="utf8") as f:
    DEV_REQUIREMENTS = f.readlines()

setup(
    name="legacy-scrobbler",
    version="0.1",
    description="Scrobbler client using the legacy Audioscrobbler protocol 1.2",
    author="jlieth",
    url="https://github.com/jlieth/legacy-scrobbler",
    license="GNU General Public License v3 (GPLv3)",
    packages=find_packages(exclude=["tests", "*.tests", "*.tests.*"]),
    python_requires=">=3.6",
    install_requires=REQUIREMENTS,
    tests_require=DEV_REQUIREMENTS,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3",
    ],
)
