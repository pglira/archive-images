from setuptools import setup, find_packages

required_packages = ['PIL']

setup(
    name='archiveImages',
    version='0.1',
    description='Archive images based on exif timestamp.',
    author='Philipp Glira',
    author_email='philipp.glira@gmail.com',
    classifiers=[
        'Natural Language :: English',
        'Development Status :: 4 - Beta',
        'Programming Language :: Python :: 3.6',
    ],
    packages=find_packages(),
    install_requires=required_packages,
    entry_points={
        'console_scripts': [
            'archiveImages=archiveImages',
        ],
    },
)
