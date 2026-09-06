"""SPA 静态托管测试:配置 static_dir 后托管前端构建产物;/api 路径不兜底。"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tradewinds.api.app import mount_spa


def _dist(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>demo-index</html>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    return dist


def test_spa_serves_index_for_root_and_client_routes(tmp_path) -> None:
    app = FastAPI()
    mount_spa(app, str(_dist(tmp_path)))
    client = TestClient(app)

    assert client.get("/").text == "<html>demo-index</html>"
    # 前端路由刷新不 404,回落 index.html
    assert client.get("/topics").text == "<html>demo-index</html>"


def test_spa_serves_static_assets(tmp_path) -> None:
    app = FastAPI()
    mount_spa(app, str(_dist(tmp_path)))
    client = TestClient(app)

    response = client.get("/assets/app.js")
    assert response.status_code == 200
    assert "console.log" in response.text


def test_spa_does_not_shadow_api_paths(tmp_path) -> None:
    app = FastAPI()
    mount_spa(app, str(_dist(tmp_path)))
    client = TestClient(app)

    # /api 未知路径保持 404 语义,不返回 SPA 页面
    response = client.get("/api/v1/no-such-endpoint")
    assert response.status_code == 404
    assert "demo-index" not in response.text


def test_spa_skipped_without_static_dir() -> None:
    app = FastAPI()
    mount_spa(app, "")
    client = TestClient(app)

    assert client.get("/").status_code == 404
