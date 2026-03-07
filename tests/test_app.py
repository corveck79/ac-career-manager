import json
from pathlib import Path

import app as app_module


def _setup_temp_app(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[1]
    config_src = repo_root / "config.json"
    config = json.loads(config_src.read_text(encoding="utf-8"))

    config_path = tmp_path / "config.json"
    data_path = tmp_path / "career_data.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    app_module.APP_DIR = str(tmp_path)
    app_module.CONFIG_PATH = str(config_path)
    app_module.DATA_PATH = str(data_path)
    app_module.config = config
    app_module.career = app_module.CareerManager(config)

    if data_path.exists():
        data_path.unlink()

    return app_module.app.test_client()


def test_new_career_creates_world_and_custom_cars(tmp_path):
    client = _setup_temp_app(tmp_path)
    payload = {
        "driver_name": "Tester",
        "difficulty": "pro",
        "weather_mode": "realistic",
        "custom_tracks": None,
        "custom_cars": {"gt4": ["car_gt4_a"], "gt3": ["car_gt3_a"], "wec": ["car_gt3_a"]},
    }
    r = client.post("/api/new-career", json=payload)
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "success"
    career_data = data["career_data"]
    assert "world" in career_data
    assert "events" in career_data["world"]
    assert career_data["career_settings"]["custom_cars"]["gt4"] == ["car_gt4_a"]


def test_world_feed_available_after_new_career(tmp_path):
    client = _setup_temp_app(tmp_path)
    r = client.post("/api/new-career", json={"driver_name": "Tester"})
    assert r.status_code == 200
    feed = client.get("/api/world-feed")
    assert feed.status_code == 200
    events = feed.get_json()["events"]
    assert isinstance(events, list)
    assert len(events) >= 1


def test_finish_race_updates_world_feed(tmp_path):
    client = _setup_temp_app(tmp_path)
    r = client.post("/api/new-career", json={"driver_name": "Tester"})
    assert r.status_code == 200

    r = client.post("/api/finish-race", json={"position": 2, "lap_time": "01:45.123"})
    assert r.status_code == 200

    feed = client.get("/api/world-feed")
    events = feed.get_json()["events"]
    assert any("finished P2" in (e.get("text", "")) for e in events)
