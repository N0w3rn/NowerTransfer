"""PyInstaller entry script.

PyInstaller executes its entry script as a top-level module, where the
package-relative imports in ``nowertransfer/__main__.py`` would not
resolve. This shim exists only to import the package by its absolute name.
"""

from nowertransfer.app import main

if __name__ == "__main__":
    raise SystemExit(main())
