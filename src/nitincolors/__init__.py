"""nitincolors — Nitin's colormap library for Python.

>>> import nitincolors as nc
>>> nc.MPL_terrain                      # any of the 1,000+ bundled maps
>>> nc.cmocean.deep                     # explicit collection access
>>> nc.GMT_ocean + nc.GMT_relief        # merge
>>> nc.MPL_terrain.crop(0.2, 1.0)       # crop
>>> cmap, norm = nc.WhBlGrYeRe.with_levels([0, 1, 5, 10, 25, 50], extend='max')
"""
from ._version import __version__
from .colormap import Colormap
from ._api import (
    add_dir,
    collections,
    concat,
    from_file,
    from_list,
    get,
    info,
    levels,
    list_cmaps,
    merge,
    register_all,
    register_collection,
    search,
    show,
    show_all,
    show_collection,
)
from . import _api

__all__ = [
    "Colormap", "__version__", "add_dir", "collections", "concat",
    "from_file", "from_list", "get", "info", "levels", "list_cmaps", "merge",
    "register_all", "register_collection", "search", "show", "show_all",
    "show_collection",
]


def __getattr__(name):  # PEP 562: nc.<colormap> / nc.<collection>
    return _api.module_getattr(name)


def __dir__():
    return sorted(set(__all__) | set(_api.module_dir()))
