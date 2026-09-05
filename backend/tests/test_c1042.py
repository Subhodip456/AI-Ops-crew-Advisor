import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from backend.services.data_loader import load_all
from backend.engine.disruption import analyze_disruption
from backend.engine.recommendations import find_replacements, rank_options

data=load_all()

def test_c1042_affected_pairing_and_flights():
    r=analyze_disruption("C-1042","2026-09-15",data)
    assert r["pairing_id"]=="P-2291"
    assert r["affected_flights"][:3]==["DX412-2026-09-15","DX413-2026-09-15","DX588-2026-09-15"]

def test_c2087_rejected_and_c3310_top():
    raw=find_replacements("P-2291","Captain",data)
    ranked=rank_options(raw,data)
    assert ranked["recommended"]["crew_id"]=="C-3310"
    c2087=next(x for x in ranked["rejected"] if x["crew_id"]=="C-2087")
    assert not c2087["legal"]
    assert any(c["rule"]=="RULE-DUTY-02" and c["status"]=="FAIL" for c in c2087["checks"])
    assert any("1h20m" in c.get("reason","") for c in c2087["checks"])

def test_c3310_cost_and_c2210_cost():
    ranked=rank_options(find_replacements("P-2291","Captain",data),data)
    c3310=next(x for x in ranked["legal_options"] if x["crew_id"]=="C-3310")
    c2210=next(x for x in ranked["legal_options"] if x["crew_id"]=="C-2210")
    assert c3310["cost_inr"]==18500
    assert c2210["cost_inr"]==41200
    assert c2210["delay_hours"]==3.0
