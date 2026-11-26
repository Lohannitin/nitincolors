"""Reading and writing colour-table files (.rgb, NCL / GMT style)."""
from __future__ import annotations

import os
import re

import numpy as np

_COMMENT = re.compile(r"#|/\*|;")


def read_rgb(path: str | os.PathLike) -> np.ndarray:
    """Read an .rgb colour table and return an (N, 3) float array in [0, 1].

    The parser works line by line, so comments, ``ncolors=`` headers and
    trailing colour names never leak into the table. Values are taken as
    0-255 integers when any of them exceeds 1, otherwise as 0-1 floats.
    NCL's ``-1`` placeholder rows (background/foreground in old NCL tables)
    are mapped to white for the first and black for the second.
    """
    rows = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            body = _COMMENT.split(line, maxsplit=1)[0].strip()
            if not body or "=" in body:
                continue
            tokens = body.replace(",", " ").split()
            if len(tokens) < 3:
                continue
            try:
                rows.append([float(t) for t in tokens[:3]])
            except ValueError:
                continue
    if not rows:
        raise ValueError(f"no colour rows found in {path}")

    arr = np.asarray(rows, dtype=float)
    placeholder = np.any(arr < 0, axis=1)
    valid = arr[~placeholder]
    scale = 255.0 if (valid.size and valid.max() > 1.0) else 1.0
    arr = arr / scale
    if placeholder.any():
        fills = [np.ones(3), np.zeros(3)]  # background white, foreground black
        for k, idx in enumerate(np.flatnonzero(placeholder)):
            arr[idx] = fills[k % 2]
    return np.clip(arr, 0.0, 1.0)


def write_rgb(path: str | os.PathLike, rgb: np.ndarray, name: str = "") -> None:
    """Write an (N, 3) or (N, 4) array in [0, 1] as an NCL-style .rgb file."""
    rgb = np.asarray(rgb, dtype=float)[:, :3]
    header = f"ncolors={len(rgb)}\n"
    if name:
        header = f"# {name} (written by nitincolors)\n" + header
    header += "# r g b"
    np.savetxt(path, np.rint(rgb * 255).astype(int), fmt="%d",
               header=header, comments="")
