"""Chunk discovery must not confuse CSS hashes with JS names."""

from spotapi._protocol.bundles import extract_mappings
from spotapi.session import BundleSession


def test_javascript_loader_owns_its_name_and_hash_maps() -> None:
    source = (
        'unrelated={1:"cccccccc",2:"dddddddd"};'
        'r.u=e=>(({1:"artist",2:"playlist"})[e]||e)+"."+'
        '({1:"aaaaaaaa",2:"bbbbbbbb",3:"eeeeeeee"})[e]+".js",'
        'r.miniCssF=e=>({1:"ffffffff",2:"99999999"})[e]+".css"'
    )
    hashes, names = extract_mappings(source)

    assert names == {1: "artist", 2: "playlist"}
    assert hashes == {1: "aaaaaaaa", 2: "bbbbbbbb", 3: "eeeeeeee"}
    urls = BundleSession._embedded_links({"https://cdn.test/web-player.main.js": source})

    assert any(url.endswith("artist.aaaaaaaa.js") for url in urls)
    assert any(url.endswith("3.eeeeeeee.js") for url in urls)
    assert all("cccccccc" not in url and "ffffffff" not in url for url in urls)
