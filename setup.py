#!/usr/bin/python

from setuptools import setup, find_packages
from codecs import open

with open('README.rst', 'r', 'utf-8') as fd:
    long_description = fd.read()

setup(
    name='bib_autofile',
    version='0.1.0',
    description='Automatically add file entry to bibtex file',
    long_description=long_description,
    url='https://github.com/fg1/bib_autofile',
    author='fg1',
    license='BSD',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
    ],
    keywords='bibtex',
    packages=find_packages(),
    install_requires=['bibtexparser', 'clint'],
    entry_points={
        'console_scripts': [
            'bib_autofile=bib_autofile:main',
        ],
    }, )
