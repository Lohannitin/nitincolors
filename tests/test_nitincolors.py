import json
import os
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402

import nitincolors as nc  # noqa: E402
from nitincolors._io import read_rgb  # noqa: E402

HERE = os.path.dirname(__file__)
ALL = nc.list_cmaps()


# ---------------------------------------------------------------- the data
def test_counts():
    assert len(ALL) == 983
    assert len(nc.collections()) == 11


@pytest.mark.parametrize("name", ALL)
def test_every_map_loads(name):
    cm = getattr(nc, name)
    assert isinstance(cm, nc.Colormap) and cm.N >= 2
    assert np.all((cm.rgb >= 0) & (cm.rgb <= 1))
    assert getattr(nc, name + "_r").N == cm.N


def test_every_website_name_works_with_its_level_count():
    """All 896 `cmaps.X` entries on pratiman-91.github.io/colormaps resolve in
    their collection with the listed level count, except three where the
    website shows Matplotlib's map instead of the collection's (upstream bug)."""
    with open(os.path.join(HERE, "website_levels.json")) as fh:
        site = json.load(fh)
    assert len(site) == 896
    upstream_bug = {("copper", "cmasher"): 510, ("prism", "cartocolors"): 11,
                    ("rainbow", "ncar_ncl"): 188}
    for name, col, levels in site:
        assert getattr(nc, name)  # plain name works
        n = nc.get(name, collection=col).N
        assert n == upstream_bug.get((name, col), levels), (name, col)


def test_restored_tables():
    for n in ["MPL_terrain", "MPL_gist_earth", "MPL_ocean", "MPL_BrBG",
              "cmocean_deep", "CBR_drywet", "MPL_Blues"]:
        assert n in ALL
    assert nc.MPL_terrain.N == 128
    ref = matplotlib.colormaps["terrain"].resampled(128)(np.arange(128))[:, :3]
    assert np.abs(nc.MPL_terrain.rgb - ref).max() < 0.03


def test_own_data_not_matplotlib_for_clashing_names():
    assert nc.prism.N == 11            # CARTOColors prism, not Matplotlib's
    assert nc.rainbow.collection == "ncar_ncl"
    assert matplotlib.colormaps["nc.rainbow"].N == 188
    assert matplotlib.colormaps["rainbow"].N == 256   # built-in untouched


def test_collection_access_and_duplicate_name():
    assert nc.cartocolors.fall.N == 7
    assert nc.cmasher.fall.N == 256
    assert nc.cmocean.deep.collection == "cmocean"
    assert matplotlib.colormaps["fall"].N == 256
    assert matplotlib.colormaps["cartocolors.fall"].N == 7
    assert len(nc.ncar_ncl) == 272
    assert "MPL_terrain" in dir(nc.ncar_ncl)


def test_ncl_placeholder_rows():
    rgb = nc.default.rgb
    assert np.allclose(rgb[0], 1) and np.allclose(rgb[1], 0)
    assert np.allclose(rgb[2], [1, 0, 0])


def test_unknown_name_suggests():
    with pytest.raises(AttributeError, match="MPL_terrain"):
        nc.MPL_terain
    with pytest.raises(KeyError):
        nc.get("definitely_not_a_map")


def test_module_is_a_real_module():
    assert nc.__file__.endswith("__init__.py")
    assert nc.__version__ == "1.0.0"


# -------------------------------------------------------------- the methods
def test_crop():
    cm = nc.GMT_topo
    c = cm.crop(0.25, 0.75)
    assert 120 <= c.N <= 130
    assert np.allclose(c.rgb[0], cm.rgb[64], atol=1e-9)
    with pytest.raises(ValueError):
        cm.crop(0.8, 0.2)


def test_slice_and_index():
    cm = nc.GMT_topo
    assert cm[10:20].N == 10
    assert len(cm[5]) == 3


def test_shift_preserves_length_and_rotates():
    cm = nc.phase
    s = cm.shift(0.25)
    assert s.N == cm.N
    assert np.allclose(s.rgb[64], cm.rgb[0])
    assert np.allclose(cm.shift(1.0).rgb, cm.rgb)
    assert np.allclose(cm.shift(-0.25).shift(0.25).rgb, cm.rgb)


def test_discrete_and_interpolate():
    cm = nc.MPL_terrain
    d = cm.discrete(10)
    assert d.N == 10
    assert np.allclose(d.rgb[0], cm.rgb[0]) and np.allclose(d.rgb[-1], cm.rgb[-1])
    assert cm.discrete(cm.N).N == cm.N
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        assert cm.discrete(300).N == 300
        assert w
    assert nc.cartocolors.fall.interpolate(256).N == 256


def test_cut():
    cm = nc.MPL_BrBG
    assert cm.cut(0.25, "left").N < cm.N
    assert cm.cut(0.25, "right").N < cm.N
    widened = cm.cut(0.2, "centre")
    assert widened.N == cm.N
    mid = widened.rgb[cm.N // 2 - 5: cm.N // 2 + 5]
    assert np.allclose(mid, mid[0])
    assert cm.cut(-0.2, "centre").N < cm.N
    odd = nc.posneg_1
    assert odd.cut(0.3, "centre").N == odd.N


def test_reverse():
    cm = nc.MPL_terrain
    assert np.allclose(cm.reversed().rgb, cm.rgb[::-1])
    assert np.allclose(nc.MPL_terrain_r.rgb, cm.rgb[::-1])
    assert cm.reversed().name == "MPL_terrain_r"


def test_merge():
    m = nc.merge("GMT_ocean", "GMT_relief", ratios=[0.4, 0.6], n=200)
    assert m.N == 200
    assert np.allclose(m.rgb[0], nc.GMT_ocean.rgb[0])
    assert np.allclose(m.rgb[-1], nc.GMT_relief.rgb[-1])
    assert (nc.GMT_ocean + nc.GMT_relief).N == 256
    assert nc.merge(["amwg256", nc.cmocean.deep, "viridis"], n=99).N == 99
    assert nc.MPL_terrain.merge("MPL_ocean", ratios=[3, 1]).N == 256
    c = nc.concat(["GMT_ocean", "GMT_relief"], ratios=[0.5, 0.5], discrete=100)
    assert c.N == 100
    with pytest.raises(ValueError):
        nc.merge("GMT_ocean")


def test_with_levels_and_contourf():
    lev = [0, 2.5, 7.5, 15, 35, 65, 115, 205]
    cmap, norm = nc.WhBlGrYeRe.with_levels(lev, extend="max")
    assert cmap.N == len(lev) - 1 and norm.boundaries.tolist() == lev
    x, y = np.meshgrid(np.linspace(0, 1, 30), np.linspace(0, 1, 30))
    fig, ax = plt.subplots()
    ax.contourf(x, y, 250 * x * y, levels=lev, cmap=cmap, norm=norm, extend="max")
    plt.close(fig)
    cmap2, _ = nc.levels("MPL_terrain", [0, 1, 2, 3], extend="both")
    assert cmap2.N == 3


def test_light_dark_with_color():
    cm = nc.MPL_terrain
    assert np.all(cm.lighten(0.5).rgb >= cm.rgb - 1e-12)
    assert np.all(cm.darken(0.5).rgb <= cm.rgb + 1e-12)
    w = cm.discrete(10).with_color("white", "start")
    assert np.allclose(w.rgb[0], 1)
    assert np.allclose(cm.with_color("k", "end", 3).rgb[-3:], 0)


def test_from_list_and_file_roundtrip(tmp_path):
    cm = nc.from_list(["white", "#9ecae1", "navy"], n=50, name="rain")
    assert cm.N == 50 and cm.name == "rain"
    assert nc.from_list(["red", "blue"]).N == 2
    p = cm.save(str(tmp_path / "rain.rgb"))
    back = nc.from_file(p)
    assert back.N == 50 and np.abs(back.rgb - cm.rgb).max() <= 0.5 / 255 + 1e-9
    cm.save(str(tmp_path / "rain.txt"))
    assert len((tmp_path / "rain.txt").read_text().split()) == 50
    assert np.allclose(read_rgb(p), back.rgb)


def test_add_dir(tmp_path):
    nc.from_list(["red", "green", "blue"]).save(str(tmp_path / "my_map.rgb"))
    assert nc.add_dir(str(tmp_path)) == ["my_map"]
    assert nc.my_map.N == 3 and nc.my_map_r.N == 3


def test_string_names_in_matplotlib():
    nc.MPL_terrain
    fig, ax = plt.subplots()
    ax.imshow(np.random.rand(4, 4), cmap="MPL_terrain")
    plt.close(fig)
    assert nc.register_collection("cmocean") == 36
    assert "deep_r" in matplotlib.colormaps


def test_search_info_list():
    assert nc.search("terrain") == ["MPL_terrain"]
    assert "GMT_topo" in nc.search("GMT_*")
    assert set(nc.list_cmaps("cmocean")) >= {"deep", "ice", "thermal"}
    i = nc.info("MPL_terrain")
    assert i["N"] == 128 and i["collection"] == "ncar_ncl"
    assert nc.get("viridis").N == 256


def test_show_functions():
    plt.close(nc.MPL_terrain.show())
    plt.close(nc.show("MPL_terrain", "GMT_topo", nc.cmocean.deep))
    plt.close(nc.show_collection("tableau"))
