"""The :class:`Colormap` object returned by every nitincolors lookup."""
from __future__ import annotations

import warnings
from typing import Iterable, Sequence

import numpy as np
from matplotlib import colors as mcolors

from ._io import write_rgb

_EXTEND_EXTRA = {"neither": 0, "min": 1, "max": 1, "both": 2}


def _unit(x: float, what: str) -> float:
    if not 0.0 <= x <= 1.0:
        raise ValueError(f"{what} must be in [0, 1], got {x}")
    return float(x)


class Colormap(mcolors.ListedColormap):
    """A Matplotlib ``ListedColormap`` with extra editing methods.

    It can be passed anywhere Matplotlib accepts a colormap
    (``cmap=...`` in ``imshow``, ``contourf``, ``pcolormesh``, cartopy,
    xarray ``.plot``...). Every editing method returns a *new* Colormap,
    so the bundled maps are never modified in place.
    """

    def __init__(self, colors, name: str = "nitincolors",
                 collection: str | None = None):
        arr = np.asarray(colors, dtype=float)
        if arr.ndim != 2 or arr.shape[1] not in (3, 4) or len(arr) < 1:
            raise ValueError("colors must be an (N, 3) or (N, 4) array")
        if arr.min() < 0 or arr.max() > 1:
            raise ValueError("colour values must lie in [0, 1]")
        super().__init__(arr, name=name)
        self._arr = arr
        self.collection = collection

    # ------------------------------------------------------------------ basics
    def _new(self, arr, suffix: str | None = None, name: str | None = None):
        if name is None:
            name = self.name if suffix is None else f"{self.name}_{suffix}"
        return Colormap(arr, name=name, collection=self.collection)

    @property
    def rgb(self) -> np.ndarray:
        """(N, 3) array of RGB values in [0, 1]."""
        return self._arr[:, :3].copy()

    def __len__(self) -> int:
        return self.N

    def __repr__(self) -> str:
        col = f", {self.collection}" if self.collection else ""
        return f"<nitincolors.Colormap '{self.name}' N={self.N}{col}>"

    def __getitem__(self, item):
        """``cm[i]`` -> one RGB(A) tuple; ``cm[a:b]`` or ``cm[idx]`` -> Colormap."""
        if isinstance(item, (int, np.integer)):
            return tuple(self._arr[item])
        arr = self._arr[item]
        if arr.ndim != 2 or len(arr) == 0:
            raise IndexError("selection must contain at least one colour")
        return self._new(arr, "sliced")

    def __add__(self, other):
        """``cm1 + cm2`` merges two maps end to end (equal shares)."""
        from ._api import merge
        return merge(self, other)

    def copy(self):
        return self._new(self._arr.copy())

    # --------------------------------------------------------------- reshaping
    def reversed(self, name: str | None = None):
        """Reverse the colour order."""
        if name is None:
            name = self.name[:-2] if self.name.endswith("_r") else self.name + "_r"
        return self._new(self._arr[::-1], name=name)

    reverse = reversed

    def crop(self, start: float = 0.0, stop: float = 1.0):
        """Keep only the part of the map between fractions ``start`` and ``stop``.

        ``cm.crop(0.2, 0.9)`` drops the first 20 % and the last 10 %.
        """
        start, stop = _unit(start, "start"), _unit(stop, "stop")
        if stop <= start:
            raise ValueError("stop must be greater than start")
        pos = np.linspace(0.0, 1.0, self.N)
        keep = (pos >= start - 1e-12) & (pos <= stop + 1e-12)
        if keep.sum() < 2:
            raise ValueError("crop range keeps fewer than 2 colours; "
                             "use .interpolate() first for very short maps")
        return self._new(self._arr[keep], "crop")

    def cut(self, ncut: float, loc: str = "centre"):
        """Remove (or, for the centre, widen) a portion of the map.

        loc='left'   : drop the first ``ncut`` fraction.
        loc='right'  : drop the last ``ncut`` fraction.
        loc='centre' : ``ncut > 0`` widens the neutral centre band of a
                       diverging map (N is preserved); ``ncut < 0`` removes
                       the central ``|ncut|`` fraction (N shrinks).
        """
        if not -1.0 <= ncut <= 1.0:
            raise ValueError("ncut must be between -1 and 1")
        loc = {"center": "centre"}.get(loc, loc)
        if loc not in ("left", "right", "centre"):
            raise ValueError("loc must be 'left', 'right' or 'centre'")
        if ncut == 0:
            return self.copy()
        if loc == "left":
            return self.crop(abs(ncut), 1.0)
        if loc == "right":
            return self.crop(0.0, 1.0 - abs(ncut))

        n = self.N
        k = max(1, int(round(abs(ncut) * n / 2)))
        mid = n // 2
        odd = n % 2
        left = self._arr[: max(mid - k, 0)]
        right = self._arr[min(mid + k + odd, n):]
        if ncut < 0:
            arr = np.vstack([left, right])
        else:
            centre = self._arr[mid - 1: mid + 1].mean(axis=0) if n % 2 == 0 \
                else self._arr[mid]
            fill = np.repeat(centre[None, :], n - len(left) - len(right), axis=0)
            arr = np.vstack([left, fill, right])
        if len(arr) < 2:
            raise ValueError("cut removes too much of the map")
        return self._new(arr, "cut")

    def shift(self, frac: float):
        """Rotate the map by ``frac`` of its length (positive = to the right).

        Number of colours is preserved; useful for circular/phase maps.
        """
        steps = int(round(frac * self.N)) % self.N
        return self._new(np.roll(self._arr, steps, axis=0), "shift")

    def discrete(self, n: int):
        """Pick ``n`` evenly spaced colours from the map (end colours kept)."""
        n = int(n)
        if n < 1:
            raise ValueError("n must be >= 1")
        if n > self.N:
            warnings.warn(f"{self.name} has only {self.N} colours; "
                          f"interpolating to {n}", stacklevel=2)
            return self.interpolate(n)
        idx = np.rint(np.linspace(0, self.N - 1, n)).astype(int)
        return self._new(self._arr[idx], f"{n}")

    def interpolate(self, n: int = 256):
        """Smoothly resample to ``n`` colours by linear interpolation in RGB."""
        n = int(n)
        if n < 1:
            raise ValueError("n must be >= 1")
        if self.N == 1 or n == 1:
            return self._new(np.repeat(self._arr[:1], n, axis=0), "interp")
        x_old = np.linspace(0.0, 1.0, self.N)
        x_new = np.linspace(0.0, 1.0, n)
        arr = np.column_stack([np.interp(x_new, x_old, self._arr[:, c])
                               for c in range(self._arr.shape[1])])
        return self._new(arr, "interp")

    def resampled(self, lutsize: int):
        """Matplotlib-compatible resample (nearest colour), stays a Colormap."""
        arr = np.asarray(super().resampled(lutsize).colors, float)
        return self._new(arr)

    # ---------------------------------------------------------------- editing
    def merge(self, *others, ratios: Sequence[float] | None = None,
              n: int | None = None, name: str | None = None):
        """Join this map with one or more others; see :func:`nitincolors.merge`."""
        from ._api import merge
        return merge(self, *others, ratios=ratios, n=n, name=name)

    def lighten(self, frac: float = 0.2):
        """Blend every colour towards white by ``frac`` (0-1)."""
        frac = _unit(frac, "frac")
        arr = self._arr.copy()
        arr[:, :3] = arr[:, :3] + (1.0 - arr[:, :3]) * frac
        return self._new(arr, "light")

    def darken(self, frac: float = 0.2):
        """Blend every colour towards black by ``frac`` (0-1)."""
        frac = _unit(frac, "frac")
        arr = self._arr.copy()
        arr[:, :3] = arr[:, :3] * (1.0 - frac)
        return self._new(arr, "dark")

    def with_color(self, color="white", at: str = "start", n: int = 1):
        """Replace ``n`` colours at 'start', 'centre' or 'end' with ``color``.

        Typical use: a white first bin for rainfall maps,
        ``nc.WhBlGrYeRe.discrete(10).with_color('white', 'start')``.
        """
        n = int(n)
        if not 1 <= n <= self.N:
            raise ValueError(f"n must be between 1 and {self.N}")
        rgba = np.asarray(mcolors.to_rgba(color))[: self._arr.shape[1]]
        arr = self._arr.copy()
        if at == "start":
            arr[:n] = rgba
        elif at == "end":
            arr[-n:] = rgba
        elif at in ("centre", "center"):
            lo = (self.N - n) // 2
            arr[lo: lo + n] = rgba
        else:
            raise ValueError("at must be 'start', 'centre' or 'end'")
        return self._new(arr)

    # --------------------------------------------------------------- plotting
    def with_levels(self, levels: Iterable[float], extend: str = "neither"):
        """Return ``(cmap, norm)`` for contour/pcolormesh with (uneven) levels.

        Colours are spread evenly over the whole map, one per bin, plus
        one for each extended end::

            lev = [0, 2.5, 7.5, 15, 35, 65, 115, 205]
            cmap, norm = nc.WhBlGrYeRe.with_levels(lev, extend='max')
            ax.contourf(lon, lat, rain, levels=lev, cmap=cmap, norm=norm,
                        extend='max')
        """
        levels = np.asarray(list(levels), dtype=float)
        if levels.ndim != 1 or len(levels) < 2 or np.any(np.diff(levels) <= 0):
            raise ValueError("levels must be a strictly increasing sequence")
        if extend not in _EXTEND_EXTRA:
            raise ValueError("extend must be 'neither', 'min', 'max' or 'both'")
        ncol = len(levels) - 1 + _EXTEND_EXTRA[extend]
        cols = self.discrete(ncol)._arr if ncol <= self.N else \
            self.interpolate(ncol)._arr
        cmap, norm = mcolors.from_levels_and_colors(levels, cols, extend=extend)
        cmap.name = f"{self.name}_levels"
        return cmap, norm

    def show(self, ax=None, width: float = 6.0, height: float = 0.6,
             label: bool = True):
        """Draw the colour strip; returns the Matplotlib figure."""
        import matplotlib.pyplot as plt
        if ax is None:
            fig, ax = plt.subplots(figsize=(width, height))
        else:
            fig = ax.figure
        ax.imshow(self._arr[None, :, :], aspect="auto",
                  interpolation="nearest", extent=(0, 1, 0, 1))
        ax.set_axis_off()
        if label:
            ax.set_title(f"{self.name}  (N={self.N})", fontsize=10, loc="left")
        return fig

    def register(self, name: str | None = None, force: bool = True):
        """Register in Matplotlib so ``cmap='<name>'`` strings work."""
        import matplotlib
        name = name or self.name
        matplotlib.colormaps.register(self, name=name, force=force)
        return name

    # ----------------------------------------------------------------- export
    def to_hex(self, keep_alpha: bool = False) -> list[str]:
        return [mcolors.to_hex(c, keep_alpha=keep_alpha) for c in self._arr]

    def to_rgb255(self) -> np.ndarray:
        return np.rint(self.rgb * 255).astype(int)

    def save(self, path: str, fmt: str | None = None) -> str:
        """Save as NCL-style ``.rgb`` (default) or a ``.txt``/``.hex`` list."""
        fmt = (fmt or path.rsplit(".", 1)[-1]).lower()
        if fmt == "rgb":
            write_rgb(path, self._arr, self.name)
        elif fmt in ("txt", "hex"):
            with open(path, "w") as fh:
                fh.write("\n".join(self.to_hex()) + "\n")
        else:
            raise ValueError("fmt must be 'rgb', 'txt' or 'hex'")
        return path
