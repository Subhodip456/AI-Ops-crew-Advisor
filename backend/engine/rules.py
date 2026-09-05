from datetime import datetime, timedelta, date
from typing import Any


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def hours(td: timedelta) -> float:
    return td.total_seconds() / 3600.0


def fmt_hours(h: float) -> str:
    sign = "-" if h < 0 else ""
    m = round(abs(h) * 60)
    return f"{sign}{m // 60}h{m % 60:02d}m"


def rule_map(rules_json: dict[str, Any]):
    return {r["rule_id"]: r for r in rules_json["rules"]}


def duty_period(day: dict[str, Any]):
    report = parse_dt(day["report_utc"])
    release = parse_dt(day["release_utc"])
    return report, release, hours(release - report)


def fdp_limit(sectors: int, rules_json: dict[str, Any]) -> float:
    p = rule_map(rules_json)["RULE-FDP-01"]["params"]
    return p["base_fdp_hours"] - max(0, sectors - p["free_sectors"]) * p["reduction_per_extra_sector_hours"]


def check_fdp(day, rules_json):
    _, _, actual = duty_period(day)
    limit = fdp_limit(len(day["flights"]), rules_json)
    ok = actual <= limit + 1e-9
    return {"rule":"RULE-FDP-01","status":"PASS" if ok else "FAIL", "actual_hours":round(actual,2), "limit_hours":round(limit,2), "reason":f"FDP {fmt_hours(actual)} <= {fmt_hours(limit)}" if ok else f"FDP {fmt_hours(actual)} exceeds {fmt_hours(limit)}"}


def history_sum(clock, start: date, end: date, kind: str):
    total = 0.0
    for row in clock["daily_history"]:
        d = date.fromisoformat(row["date"])
        if start <= d <= end:
            total += row[kind]
    return total


def check_duty_window(clock, assignment_days, rules_json):
    p = rule_map(rules_json)["RULE-DUTY-02"]["params"]
    max_h = p["max_duty_hours"]
    n = p["window_days"]
    added = {date.fromisoformat(d["date"]): duty_period(d)[2] for d in assignment_days}
    results=[]
    for duty_date, add_h in sorted(added.items()):
        start = duty_date - timedelta(days=n-1)
        base = history_sum(clock, start, duty_date, "duty_hours")
        total = base + sum(v for d,v in added.items() if start <= d <= duty_date)
        ok = total <= max_h + 1e-9
        results.append({"rule":"RULE-DUTY-02","status":"PASS" if ok else "FAIL","date":duty_date.isoformat(),"total_hours":round(total,2),"limit_hours":max_h,"reason":f"{fmt_hours(total)} / {fmt_hours(max_h)}" if ok else f"Would exceed 60h/7d by {fmt_hours(total-max_h)} ({total:.2f}h)"})
    return results


def check_flight_window(clock, assignment_days, rules_json):
    p = rule_map(rules_json)["RULE-FLT-03"]["params"]
    max_h=p["max_flight_hours"]; n=p["window_days"]
    added={date.fromisoformat(d["date"]): d.get("block_hours",0.0) for d in assignment_days}
    # Caller supplies block hours per day in assignment_days.
    results=[]
    for duty_date in sorted(added):
        start=duty_date-timedelta(days=n-1)
        base=history_sum(clock,start,duty_date,"flight_hours")
        total=base+sum(v for d,v in added.items() if start<=d<=duty_date)
        ok=total<=max_h+1e-9
        results.append({"rule":"RULE-FLT-03","status":"PASS" if ok else "FAIL","date":duty_date.isoformat(),"total_hours":round(total,2),"limit_hours":max_h,"reason":f"{total:.2f}h / {max_h}h" if ok else f"Would exceed 100h/28d by {fmt_hours(total-max_h)}"})
    return results


def check_rest(existing_days, new_days, rules_json):
    min_rest=rule_map(rules_json)["RULE-REST-04"]["params"]["min_rest_hours"]
    all_days=[]
    for d in existing_days+new_days:
        report,release,_=duty_period(d)
        all_days.append((report,release,d.get("date")))
    all_days.sort()
    results=[]
    for i in range(1,len(all_days)):
        prev=all_days[i-1]; cur=all_days[i]
        rest=hours(cur[0]-prev[1])
        if cur[2] in {x.get("date") for x in new_days}:
            ok=rest>=min_rest-1e-9
            results.append({"rule":"RULE-REST-04","status":"PASS" if ok else "FAIL","date":cur[2],"rest_hours":round(rest,2),"limit_hours":min_rest,"reason":f"Rest {fmt_hours(rest)}" if ok else f"Only {fmt_hours(rest)} rest before duty on {cur[2]}"})
    return results
