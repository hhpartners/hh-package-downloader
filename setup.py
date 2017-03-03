from setuptools import setup

setup(
    name='hh-package-downloader',
    version='0.0.1-dev01',
    py_modules=['download'],
    include_package_data=True,
    install_requires=[
        'bs4',
        'click',
        'requests'
    ],
    entry_points='''
        [console_scripts]
        hhdown=download:cli
    ''',
)
