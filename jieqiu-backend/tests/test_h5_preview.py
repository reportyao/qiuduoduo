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
