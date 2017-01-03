import os
from setuptools import setup

setup(
    name = 'dropchat',
    version = '0.1.0',
    description = 'Drop Chat',
    long_description = 'Drop Chat - Secure Disposable Chat',
    url = '',
    license = 'MIT',
    author = 'Alejandro Caceres',
    author_email = 'contact@hyperiongray.com',
    packages = [''],
    include_package_data = True,
    install_requires = ["flask", "stem"],
    classifiers = [ 'Development Status :: 4 - Beta',
                    'Programming Language :: Python :: 3',
                    'Programming Language :: Python'],
    entry_points = { 'console_scripts':
                        [ 'dropchat = runserver:main']}
)
