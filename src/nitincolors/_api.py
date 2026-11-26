"""Module-level functions of nitincolors."""
from __future__ import annotations

import difflib
import fnmatch
import os
from glob import glob
from typing import Iterable, Sequence

import matplotlib
import numpy as np
from matplotlib import colors as mcolors

from . import _registry
from ._io import read_rgb
from .colormap import Colormap

_FLAT, _BY_COL = _registry.build()
_USER: dict[str, str] = {}            # name -> path of user-supplied tables
_CACHE: dict[tuple[str | None, str], Colormap] = {}
# Matplotlib's own names are never overwritten when registering strings;
# a clashing nitincolors map is registered as "nc.<name>" instead.
_MPL_BUILTIN = frozenset(matplotlib.colormaps)


# --------------------------------------------------------------------- lookup
def _load(name: str, path: str, collection: str | None) -> Colormap:
    key = (collection, name)
    if key not in _CACHE:
        cm = Colormap(read_rgb(path), name=name, collection=collection)
        _CACHE[key] = cm
        _register_string(cm)
    return _CACHE[key]


def _string_name(cm: Colormap) -> str:
    """Matplotlib string under which a map is registered.

    Plain name when free; ``nc.<name>`` if Matplotlib already owns it;
    ``<collection>.<name>`` for the non-default copy of a duplicated name.
    """
    base = cm.name[:-2] if cm.name.endswith("_r") else cm.name
    owner = _FLAT.get(base, (None,))[0]
    if cm.collection in _registry.COLLECTIONS and owner not in (None, cm.collection):
        return f"{cm.collection}.{cm.name}"
    return cm.name if cm.name not in _MPL_BUILTIN else f"nc.{cm.name}"


def _register_string(cm: Colormap) -> None:
    import warnings
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            matplotlib.colormaps.register(cm, name=_string_name(cm), force=True)
    except Exception:  # registration is a convenience, never fatal
        pass


def _resolve(name: str, collection: str | None = None) -> Colormap:
    if collection is not None:
        if collection not in _BY_COL:
            raise KeyError(f"unknown collection '{collection}'; "
                           f"choose from {list(_BY_COL)}")
        entries = _BY_COL[collection]
        if name in entries:
            return _load(name, entries[name], collection)
    else:
        if name in _USER:
            return _load(name, _USER[name], "user")
        if name in _FLAT:
            col, path = _FLAT[name]
            return _load(name, path, col)

    if name.endswith("_r") and len(name) > 2:
        try:
            base = _resolve(name[:-2], collection)
        except KeyError:
            pass
        else:
            key = (base.collection, name)
            if key not in _CACHE:
                _CACHE[key] = base.reversed(name)
                _register_string(_CACHE[key])
            return _CACHE[key]
    raise KeyError(name)


def _suggest(name: str) -> str:
    rev = name.endswith("_r")
    base = name[:-2] if rev else name
    close = difflib.get_close_matches(base, list(_FLAT) + list(_USER), n=4,
                                      cutoff=0.6)
    if not close:
        close = [n for n in _FLAT if base.lower() in n.lower()][:4]
    if rev:
        close = [c + "_r" for c in close]
    return f" Did you mean: {', '.join(close)}?" if close else ""


def get(name, collection: str | None = None) -> Colormap:
    """Return a colormap by name (or convert any Matplotlib colormap).

    >>> nc.get('MPL_terrain')
    >>> nc.get('fall', collection='cartocolors')
    >>> nc.get('viridis')          # Matplotlib built-ins work too
    """
    if isinstance(name, Colormap):
        return name
    if isinstance(name, mcolors.Colormap):
        return _from_mpl(name)
    try:
        return _resolve(name, collection)
    except KeyError:
        pass
    if collection is None and name in matplotlib.colormaps:
        return _from_mpl(matplotlib.colormaps[name])
    raise KeyError(f"nitincolors has no colormap named '{name}'."
                   + _suggest(name))


def _from_mpl(cmap: mcolors.Colormap) -> Colormap:
    arr = cmap(np.linspace(0.0, 1.0, cmap.N))
    return Colormap(arr[:, :3], name=cmap.name, collection="matplotlib")


class Collection:
    """Attribute access to one collection: ``nc.cmocean.deep``."""

    def __init__(self, name: str):
        self._name = name

    def __getattr__(self, item: str) -> Colormap:
        if item.startswith("__"):
            raise AttributeError(item)
        try:
            return _resolve(item, self._name)
        except KeyError:
            raise AttributeError(
                f"collection '{self._name}' has no colormap '{item}'") from None

    def __dir__(self):
        return sorted(_BY_COL[self._name])

    def __iter__(self):
        return (getattr(self, n) for n in sorted(_BY_COL[self._name]))

    def __len__(self):
        return len(_BY_COL[self._name])

    def __repr__(self):
        return f"<nitincolors collection '{self._name}': {len(self)} colormaps>"

    def list(self) -> list[str]:
        return sorted(_BY_COL[self._name])

    def show(self, **kw):
        return show_collection(self._name, **kw)


_COLLECTION_OBJS = {c: Collection(c) for c in _registry.COLLECTIONS}


# ------------------------------------------------------------------ discovery
def collections() -> list[str]:
    """Names of the bundled collections."""
    return list(_registry.COLLECTIONS)


def list_cmaps(collection: str | None = None, reversed: bool = False) -> list[str]:
    """Sorted colormap names, optionally for one collection."""
    if collection is None:
        names = set(_FLAT) | set(_USER)
    elif collection == "user":
        names = set(_USER)
    else:
        if collection not in _BY_COL:
            raise KeyError(f"unknown collection '{collection}'")
        names = set(_BY_COL[collection])
    names = sorted(names, key=str.lower)
    if reversed:
        names = sorted(names + [n + "_r" for n in names], key=str.lower)
    return names


def search(pattern: str, collection: str | None = None) -> list[str]:
    """Case-insensitive search; plain text matches substrings, or use * ? wildcards.

    >>> nc.search('terrain')   ->  ['MPL_terrain']
    >>> nc.search('GMT_*')
    """
    pool = list_cmaps(collection)
    pat = pattern.lower()
    if not any(ch in pat for ch in "*?["):
        pat = f"*{pat}*"
    return [n for n in pool if fnmatch.fnmatch(n.lower(), pat)]


def info(name: str) -> dict:
    """Name, collection, number of colours and source file of a colormap."""
    cm = get(name)
    path = _USER.get(name) or _FLAT.get(name.removesuffix("_r"), (None, None))[1]
    return {"name": cm.name, "collection": cm.collection, "N": cm.N,
            "file": path}


# ------------------------------------------------------------------- creation
def _as_list(cmaps) -> list:
    if len(cmaps) == 1 and isinstance(cmaps[0], (list, tuple)):
        return list(cmaps[0])
    return list(cmaps)


def merge(*cmaps, ratios: Sequence[float] | None = None,
          trim: float | Sequence[float] = 0.0, n: int | None = None,
          name: str | None = None) -> Colormap:
    """Join two or more colormaps end to end.

    Parameters
    ----------
    *cmaps : names, nitincolors/Matplotlib colormaps (or one list of them)
    ratios : share of the output for each input; any positive numbers,
             normalised to sum to 1 (default: equal shares)
    trim   : fraction removed from *each end* of every input before joining
             (scalar or one value per map, each < 0.5)
    n      : total number of colours in the result (default 256)
    name   : name of the new map

    >>> topo = nc.merge('GMT_ocean', 'GMT_relief', ratios=[0.35, 0.65])
    >>> topo = nc.GMT_ocean + nc.GMT_relief     # equal shares
    """
    items = [get(c) for c in _as_list(cmaps)]
    if len(items) < 2:
        raise ValueError("merge needs at least two colormaps")
    k = len(items)
    r = np.ones(k) if ratios is None else np.asarray(ratios, dtype=float)
    if r.shape != (k,) or np.any(r <= 0):
        raise ValueError(f"ratios must be {k} positive numbers")
    r = r / r.sum()
    trims = np.full(k, float(trim)) if np.isscalar(trim) else np.asarray(trim, float)
    if trims.shape != (k,) or np.any(trims < 0) or np.any(trims >= 0.5):
        raise ValueError("trim must be in [0, 0.5) for every map")

    total = 256 if n is None else int(n)
    counts = np.maximum(2, np.floor(r * total).astype(int))
    # hand the rounding remainder to the largest shares so the sum is exact
    for i in np.argsort(-(r * total - np.floor(r * total)))[: max(0, total - counts.sum())]:
        counts[i] += 1

    segs = [cm(np.linspace(t, 1.0 - t, c))[:, :3]
            for cm, t, c in zip(items, trims, counts)]
    name = name or "+".join(cm.name for cm in items)
    out = Colormap(np.vstack(segs), name=name, collection="merged")
    _register_string(out)
    return out


def concat(cnames, ratios=None, trim=0.0, discrete=256, name="concat",
           save=False) -> Colormap:
    """Same call signature as ``colormaps.utils.concat`` (kept for old scripts)."""
    out = merge(*cnames, ratios=ratios, trim=trim, n=discrete, name=name)
    if save:
        out.save(f"{name}.rgb")
    return out


def from_list(colors: Iterable, n: int | None = None,
              name: str = "custom") -> Colormap:
    """Build a map from colour names / hex codes / RGB tuples.

    ``n=None`` keeps exactly the listed colours (discrete map);
    ``n=256`` interpolates smoothly between them.

    >>> nc.from_list(['white', '#9ecae1', 'navy'], n=256, name='rain')
    """
    arr = np.asarray([mcolors.to_rgb(c) for c in colors], dtype=float)
    cm = Colormap(arr, name=name, collection="custom")
    if n is not None and n != len(arr):
        cm = cm.interpolate(n)
        cm.name = name
    _register_string(cm)
    return cm


def from_file(path: str, name: str | None = None) -> Colormap:
    """Load any .rgb colour table (NCL/GMT style, 0-1 or 0-255 values)."""
    name = name or _registry.sanitize(os.path.basename(path).rsplit(".", 1)[0])
    cm = Colormap(read_rgb(path), name=name, collection="user")
    _register_string(cm)
    return cm


def add_dir(path: str) -> list[str]:
    """Make every .rgb file in ``path`` available as ``nc.<name>``."""
    added = []
    for p in sorted(glob(os.path.join(os.path.expanduser(path), "*.rgb"))):
        name = _registry.sanitize(os.path.basename(p)[:-4])
        _USER[name] = p
        _CACHE.pop(("user", name), None)
        _CACHE.pop(("user", name + "_r"), None)
        added.append(name)
    return added


def levels(cmap, levels: Iterable[float], extend: str = "neither"):
    """Shortcut for ``get(cmap).with_levels(levels, extend)`` -> (cmap, norm)."""
    return get(cmap).with_levels(levels, extend)


# ------------------------------------------------------------------- plotting
def show(*cmaps, width: float = 7.0, row: float = 0.28, title: str | None = None):
    """Stack colour strips of the given maps (names or objects) in one figure."""
    import matplotlib.pyplot as plt
    items = [get(c) for c in _as_list(cmaps)]
    if not items:
        raise ValueError("nothing to show")
    h = 0.4 + row * len(items) + (0.35 if title else 0)
    fig, axes = plt.subplots(len(items), 1, figsize=(width, h), squeeze=False)
    fig.subplots_adjust(left=0.30, right=0.99, top=1 - (0.45 if title else 0.1) / h,
                        bottom=0.1 / h, hspace=0.35)
    for ax, cm in zip(axes[:, 0], items):
        ax.imshow(cm.rgb[None, :, :], aspect="auto", interpolation="nearest")
        ax.set_axis_off()
        ax.text(-0.01, 0.5, f"{cm.name}  ({cm.N})", ha="right", va="center",
                fontsize=8, transform=ax.transAxes)
    if title:
        fig.suptitle(title, fontsize=12)
    return fig


def show_collection(collection: str, save: str | None = None, **kw):
    """Preview every map of one collection. ``save='file.png'`` writes it out."""
    if collection not in _BY_COL:
        raise KeyError(f"unknown collection '{collection}'; choose from "
                       f"{list(_BY_COL)}")
    names = sorted(_BY_COL[collection], key=str.lower)
    fig = show(*[_resolve(n, collection) for n in names],
               title=f"{collection} ({len(names)} colormaps)", **kw)
    if save:
        fig.savefig(save, dpi=110)
    return fig


def show_all(save_dir: str | None = None, **kw) -> list:
    """One preview figure per collection; optionally saved as PNGs."""
    figs = []
    for col in _registry.COLLECTIONS:
        path = os.path.join(save_dir, f"{col}.png") if save_dir else None
        if save_dir:
            os.makedirs(save_dir, exist_ok=True)
        figs.append(show_collection(col, save=path, **kw))
    return figs


def register_all() -> int:
    """Register every bundled map (and its _r) as a Matplotlib string name."""
    count = 0
    for col, entries in _BY_COL.items():
        for name, path in entries.items():
            cm = _load(name, path, col)
            _register_string(cm.reversed())
            count += 2
    return count


def register_collection(collection: str) -> int:
    count = 0
    for name, path in _BY_COL[collection].items():
        cm = _load(name, path, collection)
        _register_string(cm.reversed())
        count += 2
    return count


# ---------------------------------------------------------- module __getattr__
def module_getattr(name: str):
    if name.startswith("__"):
        raise AttributeError(name)
    if name in _COLLECTION_OBJS:
        return _COLLECTION_OBJS[name]
    try:
        return _resolve(name)
    except KeyError:
        raise AttributeError(f"nitincolors has no colormap named '{name}'."
                             + _suggest(name)) from None


def module_dir() -> list[str]:
    return sorted(set(_FLAT) | set(_USER) | set(_COLLECTION_OBJS))


def _load_env_dirs() -> None:
    for var in ("NITINCOLORS_DIR", "CMAP_DIR"):
        for d in filter(None, os.environ.get(var, "").split(os.pathsep)):
            add_dir(d)


_load_env_dirs()
