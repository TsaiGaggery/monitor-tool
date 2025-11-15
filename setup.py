#!/usr/bin/env python3
"""Setup script for monitor-tool."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="monitor-tool",
    version="1.1.0",
    author="TsaiGaggery",
    author_email="your.email@example.com",
    description="System monitoring tool for CPU, GPU, NPU, and Memory",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/TsaiGaggery/monitor-tool",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
    ],
    python_requires=">=3.8",
    install_requires=[
        "PyQt5>=5.15.0",
        "pyqtgraph>=0.12.0",
        "psutil>=5.8.0",
        "numpy>=1.20.0",
    ],
    entry_points={
        "console_scripts": [
            "monitor-tool=ui.main_window:main",
        ],
    },
)
