from .eligibility import check_eligibility
from .rules import parse_dt, hours


def find_pairing_for_crew(crew_id, date_str, rosters):
    for p in rosters["pairings"]:
        if any(m["crew_id"]==crew_id for m in p["crew"]) and any(d["date"]==date_str for d in p["days"]):
            return p
    return None


def find_pairing(pairing_id,data):
    return next((p for p in data["rosters"]["pairings"] if p["pairing_id"]==pairing_id),None)


def enrich_pairing(pairing,data):
    first=pairing["days"][0]["flights"][0]
    f=next(x for x in data["flights"] if x["flight_id"]==first)
    p=dict(pairing); p["aircraft_type"]=f["aircraft_type"]; p["_base"]=next(m for m in pairing["crew"] if m["role"]=="Captain")["crew_id"] and next(c["base"] for c in data["crew"] if c["crew_id"]==next(m["crew_id"] for m in pairing["crew"] if m["role"]=="Captain"))
    return p


def analyze_disruption(crew_id,date_str,data,pairing_id=None):
    p=find_pairing(pairing_id,data) if pairing_id else find_pairing_for_crew(crew_id,date_str,data["rosters"])
    if not p: return {"found":False,"message":"I can't determine that reliably from the provided operational data.","missing":"No matching pairing found."}
    missing_role=next((m["role"] for m in p["crew"] if m["crew_id"]==crew_id),None)
    affected=[]
    for d in p["days"]:
        affected += d["flights"]
    return {"found":True,"crew_id":crew_id,"pairing_id":p["pairing_id"],"missing_role":missing_role,"affected_flights":affected,"pairing":p}
