import json
from pathlib import Path
from functools import lru_cache

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

@lru_cache(maxsize=1)
def load_all():
    def load(name):
        with open(DATA_DIR / name, encoding="utf-8") as f:
            return json.load(f)
    return {
        "flights": load("flights.json"),
        "crew": load("crew.json"),
        "rosters": load("rosters.json"),
        "duty_clocks": load("duty_clocks.json"),
        "reserve_pool": load("reserve_pool.json"),
        "certifications": load("certifications.json"),
        "rules": load("rules.json"),
        "costs": load("costs.json"),
        "risk_signals": load("risk_signals.json"),
    }

def by_id(items, key):
    return {x[key]: x for x in items}
