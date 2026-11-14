"""H5 预览：与 App 共用代码的静态入口，SPA 深链必须回退到 index。"""


def test_h5_preview_serves_index_and_spa_deep_link(client):
    index = client.get("/h5/")
    assert index.status_code == 200
    assert "球多多" in index.text
    assert "/h5/_expo/static/js/web/" in index.text

    deep_link = client.get("/h5/predictions/2042695")
    assert deep_link.status_code == 200
    assert "球多多" in deep_link.text


def test_h5_preview_blocks_path_traversal(client):
    assert client.get("/h5/../app/main.py").status_code in (404, 400)


def test_h5_preview_missing_asset_404s_not_html(client):
    # 缺失的 js/css 必须真 404：回退 index.html 会让旧缓存页面把 HTML 当模块
    # 加载（MIME 校验失败 → 白屏）。
    missing = client.get("/h5/_expo/static/js/web/entry-does-not-exist.js")
    assert missing.status_code == 404
    assert "text/html" not in missing.headers.get("content-type", "")

    assert client.get("/h5/assets/nope-123.css").status_code == 404
    assert client.get("/h5/favicon-not-here.ico").status_code == 404


def test_h5_preview_index_no_cache_and_assets_immutable(client):
    index = client.get("/h5/")
    assert index.headers.get("cache-control") == "no-cache"

    # index.html 引用的 entry 必须真实存在（测试环境未构建时跳过）。
    import re

    match = re.search(r'/h5/_expo/static/js/web/(entry-[a-f0-9]+\.js)', index.text)
    if not match:
        return
    entry = client.get(f"/h5/_expo/static/js/web/{match.group(1)}")
    assert entry.status_code == 200
    assert "javascript" in entry.headers.get("content-type", "")
    assert "immutable" in entry.headers.get("cache-control", "")
