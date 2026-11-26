"""Name -> file registry for the bundled colour tables."""
from __future__ import annotations

import os
from glob import glob

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# Order matters only for the one duplicated name ("fall"): later collections
# win the plain name, as in the original `colormaps` package. Every map stays
# reachable through its collection, e.g. ``nitincolors.cartocolors.fall``.
COLLECTIONS = (
    "carbonplan", "cartocolors", "cmasher", "cmocean", "colorbrewer",
    "colorcet", "cubehelix", "ncar_ncl", "scientific", "sciviz", "tableau",
)


def sanitize(name: str) -> str:
    """Turn a file stem into a valid Python attribute name."""
    if name[0].isdigit() or name.startswith("_"):
        name = "N" + name
    return name.replace("-", "_").replace("+", "_").replace(" ", "_")


def build() -> tuple[dict[str, tuple[str, str]], dict[str, dict[str, str]]]:
    """Return ``(flat, by_collection)``.

    flat:           {name: (collection, path)}
    by_collection:  {collection: {name: path}}
    """
    flat: dict[str, tuple[str, str]] = {}
    by_col: dict[str, dict[str, str]] = {}
    for col in COLLECTIONS:
        cdir = os.path.join(DATA_DIR, col)
        entries = {}
        for path in sorted(glob(os.path.join(cdir, "*.rgb"))):
            name = sanitize(os.path.basename(path)[:-4])
            entries[name] = path
            flat[name] = (col, path)
        by_col[col] = entries
    return flat, by_col
