import json, os, statistics, time
import httpx

BASE = os.environ.get("JQ_BENCH_BASE", "http://127.0.0.1:8100")
paths = [
    ("health", "/health"),
    ("health_detailed", "/health?detailed=1"),
    ("stream", "/stream?date=2026-11-05&limit=50"),
    ("on_sale", "/matches/on-sale"),
    ("pulse", "/stats/pulse?date=2026-11-05"),
    ("focus", "/matches/2042519/focus?date=2026-11-05"),
    ("today", "/recommendations/today"),
    ("personas", "/personas"),
    ("admin_html", "/admin"),
    ("admin_js", "/admin/assets/admin.js"),
]

def pct(xs, p):
    xs = sorted(xs)
    if not xs: return None
    k = min(len(xs) - 1, max(0, int(round((len(xs) - 1) * p))))
    return xs[k]

def bench(client, name, path, n=20):
    lat = []; sizes = []; code = None
    for _ in range(n):
        t = time.perf_counter()
        r = client.get(path)
        dt = (time.perf_counter() - t) * 1000
        lat.append(dt); sizes.append(len(r.content)); code = r.status_code
    return {"name": name, "code": code, "n": n, "p50_ms": round(pct(lat, .5), 1),
            "p95_ms": round(pct(lat, .95), 1), "max_ms": round(max(lat), 1),
            "avg_ms": round(statistics.mean(lat), 1), "kb": round(statistics.mean(sizes)/1024, 1)}

with httpx.Client(base_url=BASE, timeout=30) as c:
    print("=== public ===")
    for name, path in paths:
        print(json.dumps(bench(c, name, path), ensure_ascii=False))
    pw = os.environ.get("JQ_ADMIN_PASSWORD", "")
    if not pw:
        print("skip admin: JQ_ADMIN_PASSWORD not set")
        raise SystemExit(0)
    r = c.post("/admin/api/login", json={"username": "admin", "password": pw})
    print("login", r.status_code)
    csrf = r.json().get("csrf_token", "")
    c.headers["x-csrf-token"] = csrf
    print("=== admin ===")
    for name, path in [
        ("admin_overview", "/admin/api/overview"),
        ("admin_data", "/admin/api/data"),
        ("admin_ops", "/admin/api/ops"),
        ("admin_recos", "/admin/api/recommendations?limit=50"),
        ("admin_personas", "/admin/api/personas"),
        ("admin_users", "/admin/api/users"),
        ("admin_audit", "/admin/api/audit?limit=100"),
    ]:
        print(json.dumps(bench(c, name, path), ensure_ascii=False))
