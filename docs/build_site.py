"""Build docs/index.html (the colormap gallery website) from the package data.

    python docs/build_site.py

GitHub Pages serves the result at https://lohannitin.github.io/nitincolors/.
Re-run after adding or changing colour tables.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

import numpy as np  # noqa: E402

import nitincolors as nc  # noqa: E402
from nitincolors import _api  # noqa: E402

# Display order, labels and one-line credits for each collection.
COLLECTIONS = [
    ("ncar_ncl", "NCAR NCL",
     "Colour tables from the NCAR Command Language, including the MPL_, cmocean_ and CBR_ tables restored in nitincolors.",
     "https://www.ncl.ucar.edu/Document/Graphics/color_table_gallery.shtml"),
    ("cmocean", "cmocean", "Kristen Thyng's colormaps for oceanography.",
     "https://matplotlib.org/cmocean/"),
    ("colorbrewer", "ColorBrewer", "Cynthia Brewer's sequential, diverging and qualitative schemes.",
     "https://colorbrewer2.org"),
    ("scientific", "Scientific colour maps",
     "Fabio Crameri's perceptually uniform maps, designed to stay readable with colour-vision deficiency.",
     "https://www.fabiocrameri.ch/colourmaps/"),
    ("colorcet", "ColorCET", "Peter Kovesi's perceptually uniform maps.",
     "https://colorcet.holoviz.org"),
    ("cmasher", "CMasher", "Ellert van der Velden's scientific colormaps.",
     "https://github.com/1313e/CMasher"),
    ("cartocolors", "CARTOColors", "CARTO's palettes for maps and data.",
     "https://github.com/CartoDB/cartocolor"),
    ("carbonplan", "CarbonPlan", "CarbonPlan's colormaps for climate data.",
     "https://github.com/carbonplan/colormaps"),
    ("sciviz", "SciVisColor", "Colormaps from the SciVisColor project.",
     "https://sciviscolor.org"),
    ("cubehelix", "Cubehelix", "Dave Green's cubehelix schemes.",
     "https://people.phy.cam.ac.uk/dag9/CUBEHELIX/"),
    ("tableau", "Tableau", "Tableau's categorical palettes.",
     "https://www.tableau.com"),
]


def to_hex(rgb: np.ndarray) -> str:
    v = np.clip(np.rint(rgb * 255), 0, 255).astype(int)
    return "".join(f"{r:02x}{g:02x}{b:02x}" for r, g, b in v)


def build() -> str:
    assert {k for k, *_ in COLLECTIONS} == set(nc.collections()), "collection list out of date"
    out = []
    for key, label, about, url in COLLECTIONS:
        items = []
        for name in nc.list_cmaps(key):
            cm = nc.get(name, collection=key)
            plain = _api._FLAT[name][0] == key       # nitincolors.<name> gives this one
            items.append([name, to_hex(cm.rgb), int(plain)])
        out.append({"key": key, "label": label, "about": about, "url": url, "maps": items})
    data = json.dumps({"version": nc.__version__, "collections": out}, separators=(",", ":"))
    with open(os.path.join(HERE, "_template.html"), encoding="utf-8") as fh:
        html = fh.read()
    assert html.count("__DATA__") == 1
    return html.replace("__DATA__", data)


if __name__ == "__main__":
    path = os.path.join(HERE, "index.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(build())
    print(f"wrote {path} ({os.path.getsize(path) / 1e6:.2f} MB)")
