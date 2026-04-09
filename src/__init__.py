"""
Fantasy Baseball H2H Category Decision Engine
Core modules for data fetching, processing, and decision-making
"""

__version__ = "1.0.0"
__author__ = "Fantasy Baseball Engine"

from . import fetchers
from . import database
from . import processors
from . import outputs

__all__ = ['fetchers', 'database', 'processors', 'outputs']