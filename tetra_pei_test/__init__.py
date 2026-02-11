"""
TETRA PEI Automated Testing Framework

A comprehensive testing framework for TETRA radios controlled via TETRA PEI
(AT commands over TCP).
"""

__version__ = "1.0.0"
__author__ = "TETRA Test Team"

from .core.radio_connection import RadioConnection
from .core.tetra_pei import TetraPEI
from .core.test_runner import TestRunner
from .core.config_manager import ConfigManager

__all__ = [
    "RadioConnection",
    "TetraPEI",
    "TestRunner",
    "ConfigManager",
]
