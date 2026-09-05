from datetime import datetime, date
from .rules import check_fdp, check_duty_window, check_flight_window, check_rest, parse_dt


def certifications_valid(crew_id, duty_dates, certifications):
    rows=[c for c in certifications if c["crew_id"]==crew_id]
    results=[]
    for d in duty_dates:
        dd=date.fromisoformat(d)
        for c in rows:
            vf=date.fromisoformat(c["valid_from"]); vt=date.fromisoformat(c["valid_to"])
            ok=dd<=vt
            results.append({"rule":"RULE-CERT-06","status":"PASS" if ok else "FAIL","cert_type":c["cert_type"],"date":d,"valid_to":c["valid_to"],"reason":f"{c['cert_type']} valid on {d}" if ok else f"{c['cert_type']} expires before {d}"})
    return results


def get_existing_crew_days(crew_id, rosters):
    out=[]
    for p in rosters["pairings"]:
        if any(m["crew_id"]==crew_id for m in p["crew"]):
            role=next(m["role"] for m in p["crew"] if m["crew_id"]==crew_id)
            for d in p["days"]:
                out.append({**d,"pairing_id":p["pairing_id"],"role":role})
    return out


def check_eligibility(crew_id, pairing, role, assignment_days, data, allow_deadhead=True):
    crew=next((c for c in data["crew"] if c["crew_id"]==crew_id),None)
    if not crew: return {"crew_id":crew_id,"legal":False,"checks":[{"status":"FAIL","reason":"Crew not found"}]}
    checks=[]
    if crew["status"] != "active":
        checks.append({"rule":"STATUS","status":"FAIL","reason":f"Crew status is {crew['status']}"})
    # qualification
    aircraft_type=pairing.get("aircraft_type") or pairing.get("_aircraft_type")
    if aircraft_type is None:
        aircraft_type=next(f["aircraft_type"] for f in data["flights"] if f["flight_id"]==pairing["days"][0]["flights"][0])
    ok=aircraft_type in crew["ratings"]
    checks.append({"rule":"RULE-QUAL-05","status":"PASS" if ok else "FAIL","reason":f"{aircraft_type} rating present" if ok else f"No {aircraft_type} rating"})
    duty_dates=[d["date"] for d in assignment_days]
    checks += certifications_valid(crew_id,duty_dates,data["certifications"])
    for d in assignment_days:
        checks.append(check_fdp(d,data["rules"]))
    clock=next(c for c in data["duty_clocks"] if c["crew_id"]==crew_id)
    checks += check_duty_window(clock,assignment_days,data["rules"])
    # Add block hours to days for flight-hour calculation
    checks += check_flight_window(clock,assignment_days,data["rules"])
    existing=get_existing_crew_days(crew_id,data["rosters"])
    existing_dates={x["date"] for x in existing}
    overlap=[d["date"] for d in assignment_days if d["date"] in existing_dates]
    if overlap:
        checks.append({"rule":"DOUBLE-BOOKING","status":"FAIL","reason":f"Existing assignment overlaps {', '.join(overlap)}"})
    checks += check_rest(existing,assignment_days,data["rules"])
    # Reserve/base logic
    reserve=next((r for r in data["reserve_pool"] if r["crew_id"]==crew_id and assignment_days[0]["date"] in r["dates"]),None)
    positioning=None
    if reserve:
        req=parse_dt(assignment_days[0]["report_utc"])
        t=req.strftime("%H:%M")
        s=reserve["oncall_window_utc"]["start"]; e=reserve["oncall_window_utc"]["end"]
        in_window=s<=t<=e
        if crew["base"]==pairing["_base"]:
            checks.append({"rule":"RULE-BASE-07","status":"PASS" if in_window else "FAIL","reason":f"Reserve window {s}-{e} covers report {t}Z" if in_window else f"Reserve window {s}-{e}Z does not cover required report {t}Z"})
        elif allow_deadhead:
            checks.append({"rule":"RULE-BASE-07","status":"PASS","reason":"Different base; deadhead positioning required"})
        else:
            checks.append({"rule":"RULE-BASE-07","status":"FAIL","reason":"Reserve callout is from another base without deadhead"})
    elif crew["base"]==pairing["_base"]:
        checks.append({"rule":"RULE-BASE-07","status":"PASS","reason":"Crew is based at required station"})
    else:
        if allow_deadhead:
            checks.append({"rule":"RULE-BASE-07","status":"PASS","reason":"Different base; deadhead positioning required"})
        else:
            checks.append({"rule":"RULE-BASE-07","status":"FAIL","reason":"Different base and deadhead not allowed"})
    legal=all(c["status"]=="PASS" for c in checks)
    return {"crew_id":crew_id,"role":role,"legal":legal,"checks":checks}
