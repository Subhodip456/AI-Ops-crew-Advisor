from datetime import datetime, timedelta

from ..services.data_loader import load_all
from ..engine.disruption import analyze_disruption
from ..engine.recommendations import (
    find_replacements,
    rank_options,
    enrich_pairing,
)

DATA = load_all()


# ============================================================
# TIER 1 — LOOKUP & RETRIEVAL
# ============================================================

def search_crew(query=None, base=None, rank=None, crew_id=None):
    rows = DATA["crew"]

    if crew_id:
        rows = [c for c in rows if c["crew_id"] == crew_id]

    if query:
        q = query.lower()
        rows = [
            c for c in rows
            if q in (c["crew_id"] + " " + c["name"]).lower()
        ]

    if base:
        rows = [c for c in rows if c["base"] == base]

    if rank:
        rows = [c for c in rows if c["rank"] == rank]

    return rows


def search_flights(
    date=None,
    dep_station=None,
    arr_station=None,
    flight_no=None
):
    rows = DATA["flights"]

    if date:
        rows = [f for f in rows if f["date"] == date]

    if dep_station:
        rows = [
            f for f in rows
            if f["dep_station"] == dep_station
        ]

    if arr_station:
        rows = [
            f for f in rows
            if f["arr_station"] == arr_station
        ]

    if flight_no:
        rows = [
            f for f in rows
            if f["flight_no"] == flight_no
        ]

    return rows


def get_crew_schedule(crew_id):
    out = []

    for p in DATA["rosters"]["pairings"]:
        if any(m["crew_id"] == crew_id for m in p["crew"]):
            member = next(
                m for m in p["crew"]
                if m["crew_id"] == crew_id
            )

            out.append({
                "pairing_id": p["pairing_id"],
                "days": p["days"],
                "role": member["role"],
            })

    return out


def get_crew_duty_clock(crew_id):
    return next(
        (
            x
            for x in DATA["duty_clocks"]
            if x["crew_id"] == crew_id
        ),
        None
    )


def get_reserve_crew(date=None, base=None):
    rows = DATA["reserve_pool"]

    if date:
        rows = [
            r for r in rows
            if date in r["dates"]
        ]

    if base:
        rows = [
            r for r in rows
            if r["base"] == base
        ]

    crews = {
        c["crew_id"]: c
        for c in DATA["crew"]
    }

    result = []

    for r in rows:
        crew = crews.get(r["crew_id"])

        if not crew:
            continue

        result.append({
            **r,
            "rank": crew["rank"],
            "reachability_minutes": crew[
                "reachability_minutes"
            ],
        })

    return result


def get_certifications(
    crew_id=None,
    expires_before=None
):
    rows = DATA["certifications"]

    if crew_id:
        rows = [
            r for r in rows
            if r["crew_id"] == crew_id
        ]

    if expires_before:
        rows = [
            r for r in rows
            if r["valid_to"] <= expires_before
        ]

    return rows


# ============================================================
# TIER 1 — DERIVED LOOKUPS
# ============================================================

def lookup_reserve_at_station(date, base):
    """
    Direct Tier-1 lookup.

    Example:
    "Who's on reserve at BLR tomorrow?"
    """

    return get_reserve_crew(
        date=date,
        base=base
    )


def calculate_duty_hours_remaining(crew_id, date):
    """
    Returns supplied duty clock information.

    The actual legality calculation remains in the
    deterministic rules engine.
    """

    clock = get_crew_duty_clock(crew_id)

    if not clock:
        return {
            "crew_id": crew_id,
            "date": date,
            "found": False,
            "message": (
                "I can't determine that reliably from "
                "the provided operational data."
            )
        }

    return {
        "crew_id": crew_id,
        "date": date,
        "duty_clock": clock,
    }


def find_departures_in_window(
    station,
    date,
    start_time,
    end_time
):
    """
    Find supplied flights departing a station
    inside a requested UTC time window.
    """

    flights = search_flights(
        date=date,
        dep_station=station
    )

    result = []

    for flight in flights:
        departure = flight.get("departure_utc")

        if not departure:
            continue

        try:
            time_part = departure[11:16]

            if start_time <= time_part <= end_time:
                result.append(flight)

        except Exception:
            continue

    return result


def find_expiring_certifications(
    date,
    days=30
):
    """
    Deterministically calculate the expiry horizon.
    """

    try:
        start = datetime.strptime(
            date,
            "%Y-%m-%d"
        ).date()

        end = start + timedelta(days=days)

    except ValueError:
        return {
            "error": (
                "Invalid date. Expected YYYY-MM-DD."
            )
        }

    rows = []

    for cert in DATA["certifications"]:

        try:
            valid_to = datetime.strptime(
                cert["valid_to"],
                "%Y-%m-%d"
            ).date()
        except (ValueError, TypeError):
            continue

        if start <= valid_to <= end:
            rows.append(cert)

    return rows


# ============================================================
# TIER 2 — DETERMINISTIC ELIGIBILITY
# ============================================================

def check_crew_eligibility(
    crew_id,
    pairing_id,
    role=None
):
    """
    Run the deterministic eligibility engine.

    The LLM must never perform these calculations itself.
    """

    from ..engine.eligibility import check_eligibility

    pairing = next(
        (
            p
            for p in DATA["rosters"]["pairings"]
            if p["pairing_id"] == pairing_id
        ),
        None
    )

    if not pairing:
        return {
            "crew_id": crew_id,
            "pairing_id": pairing_id,
            "legal": False,
            "error": "Pairing not found."
        }

    enriched = enrich_pairing(
        pairing,
        DATA
    )

    if role is None:
        existing = next(
            (
                m
                for m in pairing["crew"]
                if m["crew_id"] == crew_id
            ),
            None
        )

        role = (
            existing["role"]
            if existing
            else "Captain"
        )

    return check_eligibility(
        crew_id,
        enriched,
        role,
        enriched["days"],
        DATA
    )


# ============================================================
# TIER 2 — CREW ABSENCE
# ============================================================

def analyze_disruption_tool(
    crew_id,
    date,
    pairing_id=None
):
    """
    Analyze a crew absence.

    Example:
    "Captain C-1042 just called in sick tomorrow."
    """

    return analyze_disruption(
        crew_id,
        date,
        DATA,
        pairing_id
    )


def simulate_crew_absence(
    crew_id,
    date,
    pairing_id=None
):
    """
    Full Tier-2 absence simulation.

    1. Identify affected pairing(s)
    2. Identify affected flights
    3. Identify missing role
    4. Find legal replacements
    5. Rank legal options
    """

    disruption = analyze_disruption(
        crew_id,
        date,
        DATA,
        pairing_id
    )

    affected_pairings = []

    if pairing_id:
        affected_pairings = [pairing_id]
    else:
        affected_pairings = [
            x.get("pairing_id")
            for x in disruption.get(
                "affected_pairings",
                []
            )
            if isinstance(x, dict)
        ]

    # Fallback if disruption returns pairing IDs
    if not affected_pairings:
        affected_pairings = [
            x
            for x in disruption.get(
                "affected_pairings",
                []
            )
            if isinstance(x, str)
        ]

    simulations = []

    for pid in affected_pairings:

        pairing = next(
            (
                p
                for p in DATA["rosters"]["pairings"]
                if p["pairing_id"] == pid
            ),
            None
        )

        if not pairing:
            continue

        member = next(
            (
                m
                for m in pairing["crew"]
                if m["crew_id"] == crew_id
            ),
            None
        )

        if not member:
            continue

        missing_role = member["role"]

        candidates = find_replacements(
            pid,
            missing_role,
            DATA
        )

        ranking = rank_options(
            candidates,
            DATA
        )

        simulations.append({
            "pairing_id": pid,
            "missing_crew_id": crew_id,
            "missing_role": missing_role,
            "candidates": candidates,
            "ranking": ranking,
        })

    return {
        "simulation_type": "crew_absence",
        "crew_id": crew_id,
        "date": date,
        "disruption": disruption,
        "pairing_simulations": simulations,
    }


# ============================================================
# TIER 2 — HYPOTHETICAL CREW MOVE
# ============================================================

def simulate_crew_move(
    crew_id,
    flight_no,
    date,
    pairing_id,
    role="Captain"
):
    """
    Evaluate a hypothetical crew movement.

    IMPORTANT:
    This function does NOT mutate the supplied dataset.

    It evaluates the crew against the pairing using
    the deterministic eligibility engine.
    """

    pairing = next(
        (
            p
            for p in DATA["rosters"]["pairings"]
            if p["pairing_id"] == pairing_id
        ),
        None
    )

    if not pairing:
        return {
            "simulation_type": "crew_move",
            "legal": False,
            "error": "Pairing not found."
        }

    flight = next(
        (
            f
            for f in DATA["flights"]
            if f["flight_no"] == flight_no
            and f["date"] == date
        ),
        None
    )

    if not flight:
        return {
            "simulation_type": "crew_move",
            "legal": False,
            "error": "Flight not found."
        }

    eligibility = check_crew_eligibility(
        crew_id=crew_id,
        pairing_id=pairing_id,
        role=role
    )

    return {
        "simulation_type": "crew_move",
        "crew_id": crew_id,
        "flight_no": flight_no,
        "date": date,
        "pairing_id": pairing_id,
        "role": role,
        "flight": flight,
        "eligibility": eligibility,
        "legal": eligibility.get(
            "legal",
            False
        ),
    }


# ============================================================
# TIER 2 — STATION CLOSURE
# ============================================================

def simulate_station_closure(
    station,
    start_utc,
    end_utc
):
    """
    Simulate the operational impact of a station closure.

    This does not invent flights or consequences.
    It only evaluates supplied flight/pairing data.
    """

    try:
        start_dt = datetime.fromisoformat(
            start_utc.replace("Z", "+00:00")
        )

        end_dt = datetime.fromisoformat(
            end_utc.replace("Z", "+00:00")
        )

    except ValueError:
        return {
            "simulation_type": "station_closure",
            "error": (
                "Invalid UTC timestamp. "
                "Use ISO-8601 format."
            )
        }

    affected_flights = []

    for flight in DATA["flights"]:

        if (
            flight.get("dep_station") != station
            and flight.get("arr_station") != station
        ):
            continue

        departure = flight.get("departure_utc")
        arrival = flight.get("arrival_utc")

        if not departure or not arrival:
            continue

        try:
            dep_dt = datetime.fromisoformat(
                departure.replace("Z", "+00:00")
            )

            arr_dt = datetime.fromisoformat(
                arrival.replace("Z", "+00:00")
            )

        except ValueError:
            continue

        overlaps = (
            dep_dt < end_dt
            and arr_dt > start_dt
        )

        if overlaps:
            affected_flights.append(flight)

    affected_flight_numbers = {
        f["flight_no"]
        for f in affected_flights
    }

    affected_pairings = []

    for pairing in DATA["rosters"]["pairings"]:

        pairing_flights = []

        for day in pairing.get("days", []):
            for flight in day.get("flights", []):
                pairing_flights.append(
                    flight
                )

        overlap = (
            affected_flight_numbers
            & set(pairing_flights)
        )

        if overlap:
            affected_pairings.append({
                "pairing_id": pairing[
                    "pairing_id"
                ],
                "affected_flights": sorted(
                    overlap
                ),
                "crew": pairing.get(
                    "crew",
                    []
                ),
            })

    affected_crew = {}

    for pairing in affected_pairings:

        for member in pairing["crew"]:

            crew_id = member["crew_id"]

            affected_crew.setdefault(
                crew_id,
                {
                    "crew_id": crew_id,
                    "pairings": [],
                }
            )

            affected_crew[crew_id][
                "pairings"
            ].append(
                pairing["pairing_id"]
            )

    return {
        "simulation_type": "station_closure",
        "station": station,
        "closure": {
            "start_utc": start_utc,
            "end_utc": end_utc,
        },
        "affected_flights": affected_flights,
        "affected_pairings": affected_pairings,
        "affected_crew": list(
            affected_crew.values()
        ),
    }


# ============================================================
# EXISTING REPLACEMENT TOOLS
# ============================================================

def find_replacement_candidates_tool(
    pairing_id,
    role
):
    return find_replacements(
        pairing_id,
        role,
        DATA
    )


def rank_replacement_options_tool(
    pairing_id,
    role
):
    candidates = find_replacements(
        pairing_id,
        role,
        DATA
    )

    return rank_options(
        candidates,
        DATA
    )


def recommend_replacement(pairing_id, role):
    """
    Tier-3 recommendation:
    Find replacement candidates and rank them
    using the deterministic recommendation engine.
    """

    candidates = find_replacements(
        pairing_id,
        role,
        DATA
    )

    ranking = rank_options(
        candidates,
        DATA
    )

    return {
        "pairing_id": pairing_id,
        "role": role,
        "recommendation": ranking.get("recommended"),
        "legal_options": ranking.get("legal_options", []),
        "rejected": ranking.get("rejected", []),
    }
# ============================================================
# TOOL DISPATCH
# ============================================================

FUNCTIONS = {

    # Tier 1
    "search_crew": search_crew,
    "search_flights": search_flights,
    "get_crew_schedule": get_crew_schedule,
    "get_crew_duty_clock": get_crew_duty_clock,
    "get_reserve_crew": get_reserve_crew,
    "get_certifications": get_certifications,

    # Tier 1 derived
    "lookup_reserve_at_station":
        lookup_reserve_at_station,

    "calculate_duty_hours_remaining":
        calculate_duty_hours_remaining,

    "find_departures_in_window":
        find_departures_in_window,

    "find_expiring_certifications":
        find_expiring_certifications,

    # Deterministic eligibility
    "check_crew_eligibility":
        check_crew_eligibility,

    # Tier 2
    "analyze_disruption":
        analyze_disruption_tool,

    "simulate_crew_absence":
        simulate_crew_absence,

    "simulate_crew_move":
        simulate_crew_move,

    "simulate_station_closure":
        simulate_station_closure,

    
   # Replacement
"find_replacement_candidates": find_replacement_candidates_tool,

"rank_replacement_options": rank_replacement_options_tool,

}


# ============================================================
# SARVAM TOOL SCHEMAS
# ============================================================

def tool_schemas():

    S = lambda props, req: {
        "type": "function",
        "function": {
            "name": "",
            "description": "",
            "parameters": {
                "type": "object",
                "properties": props,
                "required": req,
            },
        },
    }

    specs = [

        (
            "search_crew",
            "Search supplied crew records.",
            {
                "query": {"type": "string"},
                "base": {"type": "string"},
                "rank": {"type": "string"},
                "crew_id": {"type": "string"},
            },
            []
        ),

        (
            "search_flights",
            "Search supplied flight schedule.",
            {
                "date": {"type": "string"},
                "dep_station": {"type": "string"},
                "arr_station": {"type": "string"},
                "flight_no": {"type": "string"},
            },
            []
        ),

        (
            "get_crew_schedule",
            "Get rostered pairings for a crew member.",
            {
                "crew_id": {"type": "string"},
            },
            ["crew_id"]
        ),

        (
            "get_crew_duty_clock",
            "Get supplied duty and flight-hour history.",
            {
                "crew_id": {"type": "string"},
            },
            ["crew_id"]
        ),

        (
            "get_reserve_crew",
            "Get reserve crew from supplied reserve_pool data.",
            {
                "date": {"type": "string"},
                "base": {"type": "string"},
            },
            []
        ),

        (
            "get_certifications",
            "Get supplied certification records.",
            {
                "crew_id": {"type": "string"},
                "expires_before": {"type": "string"},
            },
            []
        ),

        (
            "lookup_reserve_at_station",
            "Find reserve crew at a station on a supplied date.",
            {
                "date": {"type": "string"},
                "base": {"type": "string"},
            },
            ["date", "base"]
        ),

        (
            "calculate_duty_hours_remaining",
            "Retrieve the supplied duty clock for a crew member and date.",
            {
                "crew_id": {"type": "string"},
                "date": {"type": "string"},
            },
            ["crew_id", "date"]
        ),

        (
            "find_departures_in_window",
            "Find supplied flights departing a station within a UTC time window.",
            {
                "station": {"type": "string"},
                "date": {"type": "string"},
                "start_time": {"type": "string"},
                "end_time": {"type": "string"},
            },
            [
                "station",
                "date",
                "start_time",
                "end_time",
            ]
        ),

        (
            "find_expiring_certifications",
            "Find supplied certifications expiring within a deterministic date horizon.",
            {
                "date": {"type": "string"},
                "days": {"type": "integer"},
            },
            ["date"]
        ),

        (
            "check_crew_eligibility",
            "Run deterministic crew eligibility checks.",
            {
                "crew_id": {"type": "string"},
                "pairing_id": {"type": "string"},
                "role": {"type": "string"},
            },
            ["crew_id", "pairing_id"]
        ),

        (
            "analyze_disruption",
            "Analyze a supplied crew absence against the roster.",
            {
                "crew_id": {"type": "string"},
                "date": {"type": "string"},
                "pairing_id": {"type": "string"},
            },
            ["crew_id", "date"]
        ),

        (
            "simulate_crew_absence",
            "Simulate a crew absence and evaluate affected pairings and replacement options.",
            {
                "crew_id": {"type": "string"},
                "date": {"type": "string"},
                "pairing_id": {"type": "string"},
            },
            ["crew_id", "date"]
        ),

        (
            "simulate_crew_move",
            "Evaluate a hypothetical crew movement using deterministic eligibility rules.",
            {
                "crew_id": {"type": "string"},
                "flight_no": {"type": "string"},
                "date": {"type": "string"},
                "pairing_id": {"type": "string"},
                "role": {"type": "string"},
            },
            [
                "crew_id",
                "flight_no",
                "date",
                "pairing_id",
            ]
        ),

        (
            "simulate_station_closure",
            "Simulate supplied flight and crew impact from a station closure.",
            {
                "station": {"type": "string"},
                "start_utc": {"type": "string"},
                "end_utc": {"type": "string"},
            },
            [
                "station",
                "start_utc",
                "end_utc",
            ]
        ),

        (
            "find_replacement_candidates",
            "Enumerate replacement candidates and deterministic rule results.",
            {
                "pairing_id": {"type": "string"},
                "role": {"type": "string"},
            },
            ["pairing_id", "role"]
        ),
        
        (
    "recommend_replacement",
    "Recommend the best legal replacement using deterministic operational ranking.",
    {
        "pairing_id": {"type": "string"},
        "role": {"type": "string"},
    },
    ["pairing_id", "role"]
),

        (
            "rank_replacement_options",
            "Rank legal replacement options deterministically.",
            {
                "pairing_id": {"type": "string"},
                "role": {"type": "string"},
            },
            ["pairing_id", "role"]
        ),
    ]

    result = []

    for name, desc, props, req in specs:

        x = S(props, req)

        x["function"]["name"] = name
        x["function"]["description"] = desc

        result.append(x)

    return result