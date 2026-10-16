import os

from .GDLIIIEngine import GDLIIIEngine
from .internal.GDLIIIParser import File_Format

EXAMPLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'examples')

__all__ = ["GDLIIIEngine", "File_Format", "EXAMPLES_DIR"]
