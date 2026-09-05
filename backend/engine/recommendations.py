from .eligibility import check_eligibility
from .disruption import enrich_pairing
from .rules import parse_dt, hours


def flight_map(data): return {f["flight_id"]:f for f in data["flights"]}


def candidate_pool(role,pairing,data):
    ids=[]
    for c in data["crew"]:
        if c["rank"]==role and c["status"]=="active": ids.append(c["crew_id"])
    return ids


def deadhead_info(crew,pairing,data):
    if crew["base"]==pairing["_base"]: return {"delay_hours":0.0,"deadhead_cost":0}
    first_date=pairing["days"][0]["date"]
    positioning_no="DX402" if int(first_date[-2:])%2==1 else "DX589"
    pos=next((f for f in data["flights"] if f["flight_no"]==positioning_no and f["date"]==first_date),None)
    if not pos: return {"delay_hours":None,"deadhead_cost":None,"error":"No positioning flight found in supplied data"}
    arr=parse_dt(pos["arr_utc"])
    new_report=arr.timestamp()+15*60
    scheduled=parse_dt(pairing["days"][0]["report_utc"]).timestamp()
    delay=max(0,(new_report-scheduled)/3600)
    return {"delay_hours":round(delay,2),"deadhead_cost":data["costs"]["deadhead_positioning"],"positioning_flight":pos["flight_id"]}


def find_replacements(pairing_id, role, data):
    raw=next((p for p in data["rosters"]["pairings"] if p["pairing_id"]==pairing_id),None)
    if not raw: return {"found":False,"message":"Pairing not found"}
    pairing=enrich_pairing(raw,data)
    pool=candidate_pool(role,pairing,data)
    results=[]
    for cid in pool:
        c=next(x for x in data["crew"] if x["crew_id"]==cid)
        assignment_days=[]
        for day in pairing["days"]:
            d=dict(day)
            d["block_hours"]=sum(next(f["block_hours"] for f in data["flights"] if f["flight_id"]==fid) for fid in day["flights"])
            assignment_days.append(d)
        check=check_eligibility(cid,pairing,role,assignment_days,data)
        dh=deadhead_info(c,pairing,data)
        if dh.get("error"): check["legal"]=False; check["checks"].append({"rule":"RULE-BASE-07","status":"FAIL","reason":dh["error"]})
        # reserve callout window is a legality gate when the candidate is in reserve.
        reserve=next((r for r in data["reserve_pool"] if r["crew_id"]==cid and pairing["days"][0]["date"] in r["dates"]),None)
        if reserve and c["base"]==pairing["_base"]:
            req=parse_dt(pairing["days"][0]["report_utc"]).strftime("%H:%M")
            s=reserve["oncall_window_utc"]["start"]; e=reserve["oncall_window_utc"]["end"]
            if not s<=req<=e:
                check["legal"]=False
                check["checks"].append({"rule":"RULE-BASE-07","status":"FAIL","reason":f"reserve on-call window {s}-{e}Z does not cover required report {req}Z"})
        cost= data["costs"]["reserve_callout_pilot"] if reserve and role in ("Captain","First Officer") else data["costs"]["dayoff_callout_pilot"]
        if role in ("Senior Cabin Crew","Cabin Crew"):
            cost=data["costs"]["reserve_callout_cabin"] if reserve else data["costs"]["dayoff_callout_cabin"]
        if dh.get("deadhead_cost") is not None and dh["delay_hours"] is not None:
            cost += dh["deadhead_cost"] + dh["delay_hours"]*data["costs"]["delay_cost_per_duty_hour"]
        results.append({"crew_id":cid,"legal":check["legal"],"checks":check["checks"],"cost_inr":round(cost),"delay_hours":dh.get("delay_hours",0.0),"coverage":f"{len(pairing['days'][0]['flights'])+sum(len(d['flights']) for d in pairing['days'][1:])}/{len([f for d in pairing['days'] for f in d['flights']])}","base":c["base"],"ratings":c["ratings"],"reachability_minutes":c["reachability_minutes"],"reserve":reserve})
    return {"found":True,"pairing_id":pairing_id,"role":role,"candidates":results}


def rank_options(result,data):
    legal=[r for r in result["candidates"] if r["legal"]]
    # Deterministic ranking: legal, complete coverage, qualification/rest already gates, reachability, base, cost, delay.
    def key(r):
        reserve_bonus=0 if r["reserve"] else 1
        base_penalty=0 if r["base"]==next(p["_base"] for p in [enrich_pairing(next(x for x in data["rosters"]["pairings"] if x["pairing_id"]==result["pairing_id"]),data)]) else 1
        reach=r["reachability_minutes"] if r["reachability_minutes"] is not None else 9999
        return (0, -1, reserve_bonus, base_penalty, r["cost_inr"], r["delay_hours"], reach)
    legal.sort(key=key)
    for i,r in enumerate(legal,1): r["rank"]=i
    return {"pairing_id":result["pairing_id"],"recommended":legal[0] if legal else None,"legal_options":legal,"rejected":[r for r in result["candidates"] if not r["legal"]]}
