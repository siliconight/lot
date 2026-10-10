"""site_adjacency.py -- which buildings stand beside which, and whether the guide would (Lot 0.111.0).

Roadmap 230, the walker's adjacency and layout guide
(`docs/reference/PA_1990S_ADJACENCY_AND_LAYOUT_GUIDE.md` at the factory root): a plausible town
is a network of relationships, and "can A be next to B" is answered by what kind of adjacency it
is and why. Level Factory 0.176.0 draws a lot by a cluster template when the brief asks; this is
the other half, the audit that reads the lot that WAS drawn and says, pair by pair, what the
guide makes of it -- the category affinity (housing beside heavy industry is a conflict needing
an explanation, commerce beside transport a strong fit) and the pair rules Lot can judge from an
archetype's words and the two buildings' geometry.

Report-only, as `site_audit` is: `S_ADJACENCY` at MED where the guide says `condition` or
worse, at INFO where it says `prefer` or `allow` (the reason a pair is good is worth a line too)
or the affinity is merely weak. Pure: a site spec in, findings out.

THE RELATION IS GEOMETRY, THE CATEGORY IS WORDS. Two lot buildings are `shared_boundary` when
their footprints stand within `TOUCH_M` of each other, `across_local_street` when the line between
their centres crosses a road, else `same_block`: they share the lot. The category comes from the
archetype's name, the way `building_library.anchor_families` and `cluster.by_archetype` read it,
first matching row wins; a name no row claims is commerce, the guide's largest column. The
Empties' terrace is composed by Level Factory and is not in the spec's buildings, so a lot's
houses are its twins, walk-ups and mansions.
"""
from __future__ import annotations

#: footprints this close, edge to edge, share a boundary
TOUCH_M = 3.0
#: the half-extent of a building whose spec carries no `_footprint`
DEFAULT_HALF_M = 8.0

#: Archetype words -> the guide's category; first row that matches wins, so the specific stands
#: before the general (`country_club` before `club`, `gas_station` before `station`'s transport
#: row would not matter: both are transport).
CATEGORY_WORDS = (
    (("country_club",), "rec"),
    (("strip_club", "casino", "nightclub", "night", "tavern", "club"), "ngt"),
    (("hospital", "clinic", "courthouse", "police", "funeral", "landmark", "hall", "museum",
      "school", "church", "library", "post_office"), "civ"),
    (("stadium", "arena", "marina", "park", "pool", "cinema", "arcade", "bowling", "playground"), "rec"),
    (("refinery", "factory", "foundry", "scrap", "utility", "plant"), "hvy"),
    (("warehouse", "storage", "depot", "freight", "brewery", "auto", "garage", "workshop",
      "print", "supply", "construction", "train", "yard", "body"), "lgt"),
    (("station", "airport", "parking", "bus", "truck", "gas", "fuel", "rental", "terminal"), "trn"),
    (("barn", "farm", "feed", "greenhouse", "produce"), "agr"),
    (("apartment", "twin", "rowhouse", "rowhome", "mansion", "house", "walkup", "residence"), "res"),
)
DEFAULT_CATEGORY = "ret"
CATEGORIES = ("res", "ret", "civ", "rec", "ngt", "lgt", "hvy", "trn", "agr")
#: The guide's category affinity, `district_near`, symmetric: 2 strong fit, 1 useful, 0
#: context-dependent, -1 usually weak, -2 a significant conflict requiring explanation.
AFFINITY = {
    "res": (2, 2, 2, 2, 0, 0, -2, 1, 1),
    "ret": (2, 2, 2, 2, 2, 1, -1, 2, 1),
    "civ": (2, 2, 2, 2, 0, 0, -2, 1, 1),
    "rec": (2, 2, 2, 2, 1, 0, -2, 1, 1),
    "ngt": (0, 2, 0, 1, 2, 1, -1, 1, 0),
    "lgt": (0, 1, 0, 0, 1, 2, 1, 2, 1),
    "hvy": (-2, -1, -2, -2, -1, 1, 2, 2, 0),
    "trn": (1, 2, 1, 1, 1, 2, 2, 2, 1),
    "agr": (1, 1, 1, 1, 0, 1, 0, 1, 2),
}
#: The guide's pair rules Lot can judge: (id, words of a, words of b, relations, verdict, what
#: the guide requires). Symmetric: a and b match either way round.
PAIR_RULES = (
    ("P04", ("clinic", "hospital"), ("pharmacy",), ("same_block", "across_local_street", "shared_boundary"),
     "prefer", "patients reach the pharmacy by an intelligible public route"),
    ("P06", ("school", "playground", "pool"), ("refinery", "scrap", "depot", "truck", "freight"),
     ("shared_boundary",), "condition",
     "a site history, public approaches kept off the industrial traffic, the nuisance shown honestly"),
    ("P07", ("school",), ("strip_club", "casino", "nightclub", "club"), ("shared_boundary", "across_local_street"),
     "condition", "a specific local-history premise, and queues, hours, signage and entrances resolved"),
    ("P08", ("rowhouse", "rowhome", "apartment", "walkup", "twin"),
     ("corner", "stop_n_go", "convenience", "deli", "pharmacy", "barber"),
     ("shared_boundary", "same_block", "across_local_street"), "prefer",
     "residential entry and commercial servicing both workable"),
    ("P10", ("rowhouse", "rowhome", "twin", "apartment", "walkup"), ("tavern", "bar"),
     ("shared_boundary", "same_block", "across_local_street"), "allow",
     "crowds and exterior noise scaled to a neighbourhood establishment"),
    ("P11", ("rowhouse", "rowhome", "apartment", "walkup", "mansion", "twin"),
     ("strip_club", "casino", "nightclub"), ("shared_boundary",), "condition",
     "the development history, noise exposure, queues and late departures explained"),
    ("P12", ("factory", "foundry"), ("rowhouse", "rowhome", "twin", "hall", "tavern"),
     ("same_block", "shared_boundary", "across_local_street"), "condition",
     "the employment relationship explained; homes and workers reach their doors clear of freight"),
    ("P13", ("warehouse", "factory", "foundry"), ("depot", "truck", "freight"),
     ("shared_boundary", "same_block"), "prefer", "freight on the road network with real swept paths"),
    ("P14", ("depot", "truck", "factory", "foundry", "bus"), ("deli", "diner"),
     ("same_block", "across_local_street"), "prefer", "staff or driver access to the food identified"),
    ("P17", ("station",), ("deli", "office", "apartment", "walkup"), ("same_block", "across_local_street"),
     "prefer", "an actual platform access route in the selected year"),
    ("P18", ("motel",), ("diner", "gas", "fuel", "auto", "garage"), ("shared_boundary", "across_local_street"),
     "prefer", "a coherent roadside arrival pattern"),
    ("P19", ("supermarket", "grocery"), ("pharmacy", "video", "pizza"), ("same_block",),
     "prefer", "separate tenants with any shared parking or servicing rights modelled"),
    ("P20", ("auto", "garage", "body", "supply"), ("rowhouse", "rowhome", "apartment", "walkup"),
     ("shared_boundary",), "condition", "the work's scale and history stated; residential access outside the apron"),
    ("P21", ("hospital",), ("factory", "foundry", "nightclub", "strip_club", "casino", "depot", "truck"),
     ("shared_boundary",), "condition", "patient, service and less-sensitive edges distinguished"),
    ("P28", ("courthouse",), ("office", "bank", "credit", "diner", "parking"),
     ("same_block", "across_local_street"), "prefer", "a plausible administrative centre with public connections"),
    ("P30", ("gas", "fuel"), ("playground", "pool", "school"), ("shared_boundary",),
     "condition", "children or swimmers separated from fuelling and delivery circulation"),
)
#: how a verdict is reported
SEVERITY = {"reject": "HIGH", "repair": "HIGH", "condition": "MED", "allow": "INFO", "prefer": "INFO"}
RANK = {"prefer": 0, "allow": 1, "condition": 2, "repair": 3, "reject": 4}


def category_of(archetype) -> str:
    key = str(archetype or "").strip().lower()
    for words, cat in CATEGORY_WORDS:
        if any(w in key for w in words):
            return cat
    return DEFAULT_CATEGORY


def affinity(cat_a, cat_b) -> int:
    return AFFINITY[cat_a][CATEGORIES.index(cat_b)]


def _rect(b):
    x, y = b["at"][:2]
    fp = b.get("_footprint") or b.get("footprint")
    if fp and len(fp) >= 2:
        hx, hy = float(fp[0]) / 2.0, float(fp[1]) / 2.0
        if int(round(float(b.get("rot") or 0.0))) % 180 == 90:
            hx, hy = hy, hx
    else:
        hx = hy = DEFAULT_HALF_M
    return (x - hx, y - hy, x + hx, y + hy)


def _gap(r, s) -> float:
    dx = max(s[0] - r[2], r[0] - s[2], 0.0)
    dy = max(s[1] - r[3], r[1] - s[3], 0.0)
    return (dx * dx + dy * dy) ** 0.5


def _crosses(a, b, c, d) -> bool:
    def turn(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return (turn(a, b, c) * turn(a, b, d) < 0) and (turn(c, d, a) * turn(c, d, b) < 0)


def relation(a, b, roads) -> str:
    """`shared_boundary` within TOUCH_M, `across_local_street` when a road lies between the two
    centres, else `same_block`."""
    if _gap(_rect(a), _rect(b)) <= TOUCH_M:
        return "shared_boundary"
    pa, pb = tuple(a["at"][:2]), tuple(b["at"][:2])
    for rd in roads or ():
        ra, rb = rd.get("a"), rd.get("b")
        if ra and rb and _crosses(pa, pb, tuple(ra[:2]), tuple(rb[:2])):
            return "across_local_street"
    return "same_block"


def _words(archetype):
    return str(archetype or "").strip().lower()


def rules_for(arch_a, arch_b, rel) -> list:
    """The pair rules that match these two archetypes, either way round, at this relation."""
    ka, kb = _words(arch_a), _words(arch_b)
    out = []
    for rid, wa, wb, rels, verdict, requires in PAIR_RULES:
        if rel not in rels:
            continue
        fwd = any(w in ka for w in wa) and any(w in kb for w in wb)
        back = any(w in kb for w in wa) and any(w in ka for w in wb)
        if fwd or back:
            out.append((rid, verdict, requires))
    return out


def judge(a, b, roads) -> dict:
    """One pair's verdict: the strongest matching rule's, else the affinity's (-2 a `condition`,
    -1 `weak`, else `fit`)."""
    rel = relation(a, b, roads)
    ca, cb = category_of(a.get("archetype")), category_of(b.get("archetype"))
    aff = affinity(ca, cb)
    rules = rules_for(a.get("archetype"), b.get("archetype"), rel)
    if rules:
        rid, verdict, requires = max(rules, key=lambda r: RANK[r[1]])
    else:
        rid, requires = "", ""
        verdict = "condition" if aff <= -2 else ("weak" if aff == -1 else "fit")
    return {"a": a.get("id"), "b": b.get("id"), "a_archetype": a.get("archetype"),
            "b_archetype": b.get("archetype"), "relation": rel, "categories": (ca, cb),
            "affinity": aff, "rule": rid, "verdict": verdict, "requires": requires}


def findings(site) -> list:
    """``[(severity, code, message)]`` for every pair of lot buildings the guide has something to
    say about: MED for `condition` and worse, INFO for `prefer`, `allow` and a weak affinity; a
    plain fit says nothing."""
    out = []
    bs = [b for b in site.get("buildings", []) if b.get("at")]
    roads = site.get("roads", [])
    for i, a in enumerate(bs):
        for b in bs[i + 1:]:
            j = judge(a, b, roads)
            v = j["verdict"]
            if v == "fit":
                continue
            if v == "weak":
                out.append(("INFO", "S_ADJACENCY",
                            f"{j['a']} ({j['a_archetype']}) and {j['b']} ({j['b_archetype']}) are "
                            f"{j['relation']}: {j['categories'][0]} beside {j['categories'][1]} is a "
                            f"weak fit in the guide's matrix ({j['affinity']}); context decides."))
                continue
            how = f"{j['rule']} {v}" if j["rule"] else f"affinity {j['affinity']}, {v}"
            out.append((SEVERITY[v], "S_ADJACENCY",
                        f"{j['a']} ({j['a_archetype']}) and {j['b']} ({j['b_archetype']}) are "
                        f"{j['relation']}: {how}"
                        + (f" -- {j['requires']}." if j["requires"] else
                           " -- a significant conflict the guide wants explained by ownership, history or a boundary.")))
    return out
