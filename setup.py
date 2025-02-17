import os
from setuptools import setup, find_packages

# Read the contents of your README file
def read_long_description():
    with open(os.path.join(os.path.dirname(__file__), 'README.md'), encoding='utf-8') as f:
        return f.read()

setup(
    name='dns-guesser',
    version='0.1.2',
    packages=find_packages(),
    install_requires=[
        'dnspython==2.7.0'
    ],
    entry_points={
        'console_scripts': [
            'dns-guesser = app.src.main:main',
        ],
    },
    test_suite='tests',
    python_requires='>=3.10',
    short_description='A tool to guess and resolve subdomains using DNS.',
    long_description=read_long_description(),
    long_description_content_type='text/markdown',
)