import os
from setuptools import setup, find_packages

setup(
    name = 'dropchat',
    version = '0.3.0',
    description = 'DropChat',
    long_description = 'Drop Chat - Secure Disposable Chat',
    url = '',
    license = 'MIT',
    author = 'Alejandro Caceres',
    author_email = 'contact@hyperiongray.com',
    packages = [''],
    include_package_data = True,
    package_data = {'': ['templates/*.html']},
    python_requires='>=3.8',
    install_requires = ["Flask>=3.0.0,<4.0.0", "stem>=1.8.2,<2.0.0"],
    classifiers = [ 'Development Status :: 4 - Beta',
                    'Programming Language :: Python :: 3',
                    'Programming Language :: Python :: 3.8',
                    'Programming Language :: Python :: 3.9',
                    'Programming Language :: Python :: 3.10',
                    'Programming Language :: Python :: 3.11',
                    'Programming Language :: Python :: 3.12',
                    'Programming Language :: Python'],
    entry_points = { 'console_scripts':
                        [ 'dropchat = runserver:main']}
)
