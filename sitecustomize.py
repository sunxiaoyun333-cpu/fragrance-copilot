"""Make portable Python find installed site-packages when launched from this project."""

from __future__ import annotations

import sys
from pathlib import Path


def _add_portable_site_packages():
    current_python = Path(sys.executable)
    portable_site_packages = current_python.parent / "Lib" / "site-packages"
    if portable_site_packages.exists():
        site_packages_str = str(portable_site_packages)
        if site_packages_str not in sys.path:
            sys.path.insert(0, site_packages_str)


_add_portable_site_packages()
