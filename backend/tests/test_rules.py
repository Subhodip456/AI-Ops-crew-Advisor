import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from backend.services.data_loader import load_all
from backend.engine.rules import fdp_limit

def test_fdp_rule_loaded_from_rules_json():
    data=load_all(); assert fdp_limit(3,data["rules"])==12.5; assert fdp_limit(4,data["rules"])==12.0
