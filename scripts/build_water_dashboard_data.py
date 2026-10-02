#!/usr/bin/env python3
"""Pull water datasets + usage from data.ca.gov and data.cnra.ca.gov (CKAN 2.9).

Writes data/water_datasets.csv: one row per catalog record that is in the
"water" group on either portal, plus the federated copy of any such record on
the other portal (flagged in_water_group=0 when it is not grouped as water).

Federation links come from CKAN harvest metadata: a harvested copy carries
extras.guid = the id of the upstream record. Records with no harvest link are
also matched on normalized title + publisher to catch manual duplicates.

Usage numbers are CKAN's built-in tracking (package_show?include_tracking=true):
  views_total   all-time unique-visitor-days on the dataset page
  views_recent  the same over the last 14 days
  resource_views_total  summed over the dataset's resources (clicks/downloads)
API calls and direct resource-URL hits are not counted by CKAN tracking.

Stdlib only. Run from the repo root:  python3 scripts/build_water_dashboard_data.py
"""
import csv, json, re, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

PORTALS = {"dca": "https://data.ca.gov", "cnra": "https://data.cnra.ca.gov"}
UA = {"User-Agent": "CA-Open-Water-Data-Atlas/1.0 (github.com/ggearheart/CA_Open_Water_Data_Atlas)"}


def api(base, action, **params):
    url = f"{base}/api/3/action/{action}?" + urllib.parse.urlencode(params)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r:
                return json.load(r)["result"]
        except Exception as e:  # transient 5xx / timeouts
            if attempt == 4:
                raise RuntimeError(f"{url}: {e}")
            time.sleep(2 ** attempt)


def search_all(base, fq):
    out, start = [], 0
    while True:
        # Stable sort: the default (metadata_modified) shifts records between pages mid-fetch.
        res = api(base, "package_search", fq=fq, rows=1000, start=start, sort="id asc")
        out += res["results"]
        start += 1000
        if start >= res["count"]:
            return out


def extras(d):
    return {e["key"]: e["value"] for e in d.get("extras", [])}


# --- publisher groups -------------------------------------------------------
def publisher(org):
    if org in ("dwr", "california-department-of-water-resources"):
        return "DWR"
    if org in ("california-waterboards", "california-state-water-resources-control-board"):
        return "Water Boards"
    if org == "california-department-of-fish-and-wildlife":
        return "CDFW"
    if org.startswith("federal-") or org == "water-data-partners":
        return "Federal"
    return "Other"


# --- topic classifier: first match wins, in this order ----------------------
TOPICS = [
    ("Models & tools", r"\bdsm2\b|iwfm|c2vsim|calsim|wrims|\bdmug\b|\bcsdp\b|vista|eco-ptm|\bmodel(s|ing)?\b|calculator|software|\bgui\b|newsletter"),
    ("Drinking water", r"drinking water|public water system|water system|potable|ddw\b|safe drinking"),
    ("Water quality", r"water quality|ceden|swamp|contamin|bacteria|toxicity|chemistry|nutrient|harmful algal|cyanobact|pesticide|mercury|salinity|temperature monitoring|\blake\b|limnolog|\bctd\b|turbidity|tmdl|303\(d\)|impaired"),
    ("Wastewater & stormwater", r"wastewater|storm ?water|sewer|npdes|discharge|recycled water|ciwqs|smarts"),
    ("Groundwater", r"groundwater|aquifer|\bwell(s)?\b|sgma|gsp\b|basin prioritization|subsidence|casgem"),
    ("Water rights & use", r"water right|diversion|ewrims|calwatrs|water use|urban water|conservation report|water supplier|wue|water transfer|agricultural water|demand|mwelo|landscape"),
    ("Reservoirs & infrastructure", r"reservoir|state water project|\bswp\b|\bdam(s)?\b|canal|aqueduct|levee|ferc|hydropower|powerplant|pumping|delta conveyance|facility|facilities"),
    ("Ocean & coast", r"hydrographic survey|bathymetr|seafloor"),  # NOAA NOS surveys before "hydro*" streamflow terms
    ("Streamflow, snow & climate", r"stream ?flow|\bgage|gauge|discharge data|river stage|snow|precip|evapotranspiration|climate|hydrolog|hydrography|runoff|forecast|\bnwis\b|cdec"),
    ("Flood & drought", r"flood|drought|fema|inundation|dry well"),
    ("Fish, wildlife & habitat", r"\bfish|salmon|smelt|steelhead|habitat|species|wildlife|wetland|riparian|vegetation|ecosystem|invertebrate|benthic|restoration"),
    ("Ocean & coast", r"ocean|coast|marine|bathymetr|seafloor|estuar|tidal|sea level|bay\b"),
    ("Boundaries, land & mapping", r"boundar|land use|crop|lidar|imagery|elevation|parcel|atlas|bulletin 118|watershed map|huc\b|district|region"),
]
TOPIC_RX = [(t, re.compile(p, re.I)) for t, p in TOPICS]


def topic(d):
    # Title is the strongest signal; fall back to tags, then the description.
    for text in (d.get("title") or "",
                 " ".join(t["name"] for t in d.get("tags", [])),
                 (d.get("notes") or "")[:400]):
        for t, rx in TOPIC_RX:
            if rx.search(text):
                return t
    return "Other / general"


def norm_title(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def year_of(s):
    return s[:4] if s else ""


def main():
    print("Fetching catalogs…", file=sys.stderr)
    cat = {
        "dca": search_all(PORTALS["dca"], "*:*"),
        # Skip the ~16k ocean-science harvest unless it is grouped as water.
        "cnra": search_all(PORTALS["cnra"], "-organization:ocean-data-partners")
        + search_all(PORTALS["cnra"], "organization:ocean-data-partners AND groups:water"),
    }
    # The portals' search index is occasionally inconsistent between pages/replicas:
    # reconcile against a cheap id-only listing of each Water group.
    for p, rows in cat.items():
        have = {d["id"] for d in rows}
        want = set()
        start = 0
        while True:
            res = api(PORTALS[p], "package_search", fq="groups:water", rows=1000, start=start, sort="id asc", fl="id")
            want |= {d["id"] for d in res["results"]}
            start += 1000
            if start >= res["count"]:
                break
        for i in sorted(want - have):
            rows.append(api(PORTALS[p], "package_show", id=i))
            print(f"  reconciled missing {p} record {i}", file=sys.stderr)
        print(f"  {p}: {len(rows)} records", file=sys.stderr)

    rec = {}  # (portal, id) -> dataset dict
    for p, rows in cat.items():
        for d in rows:
            rec[(p, d["id"])] = d

    by_guid = {}  # upstream guid -> [(portal,id)]
    by_title = {}
    for key, d in rec.items():
        g = extras(d).get("guid")
        if g:
            by_guid.setdefault(g, []).append(key)
        by_title.setdefault((norm_title(d["title"]), publisher((d.get("organization") or {}).get("name", ""))), []).append(key)

    def twin(key):
        """Return (twin_key, how) on the other portal, or (None, '')."""
        p, i = key
        other = "cnra" if p == "dca" else "dca"
        d = rec[key]
        g = extras(d).get("guid")
        if g and (other, g) in rec:                       # I am a harvested copy of `other`
            return (other, g), "harvest"
        for k in by_guid.get(i, []):                      # `other` harvested me
            if k[0] == other:
                return k, "harvest"
        if g:
            for k in by_guid.get(g, []):                  # both harvested the same upstream
                if k[0] == other:
                    return k, "shared upstream"
        for k in by_title.get((norm_title(d["title"]), publisher((d.get("organization") or {}).get("name", ""))), []):
            if k[0] == other:
                return k, "title match"
        return None, ""

    def in_water(d):
        return any(g["name"] == "water" for g in d.get("groups", []))

    keys = {k for k, d in rec.items() if in_water(d)}
    for k in list(keys):
        t, _ = twin(k)
        if t:
            keys.add(t)
    keys = sorted(keys)
    print(f"Fetching usage for {len(keys)} records…", file=sys.stderr)

    def tracking(key):
        p, i = key
        try:
            d = api(PORTALS[p], "package_show", id=i, include_tracking="true")
        except RuntimeError as e:
            print("  !", e, file=sys.stderr)
            return key, None
        ts = d.get("tracking_summary") or {}
        rv = sum((r.get("tracking_summary") or {}).get("total", 0) for r in d.get("resources", []))
        return key, (ts.get("total", 0), ts.get("recent", 0), rv)

    with ThreadPoolExecutor(6) as ex:
        usage = dict(ex.map(tracking, keys))
    # data.ca.gov rate-limits bursts (HTTP 429): retry stragglers slowly.
    for k in [k for k, v in usage.items() if v is None]:
        time.sleep(5)
        usage[k] = tracking(k)[1]

    out = []
    for key in keys:
        p, i = key
        d = rec[key]
        ex_ = extras(d)
        org = (d.get("organization") or {}).get("name", "")
        tw, how = twin(key)
        u = usage.get(key) or ("", "", "")
        harvested_from = ""
        if ex_.get("guid"):
            if tw and how == "harvest" and tw[1] == ex_["guid"]:
                harvested_from = "data.cnra.ca.gov" if tw[0] == "cnra" else "data.ca.gov"
            else:
                harvested_from = ex_.get("harvest_source_title") or "agency GIS hub"
        out.append({
            "portal": "data.ca.gov" if p == "dca" else "data.cnra.ca.gov",
            "id": i,
            "name": d["name"],
            "title": d["title"],
            "org": org,
            "org_title": (d.get("organization") or {}).get("title", ""),
            "publisher": publisher(org),
            "topic": topic(d),
            "tags": ";".join(t["name"] for t in d.get("tags", []))[:300],
            "in_water_group": int(in_water(d)),
            "groups": ";".join(g["name"] for g in d.get("groups", [])),
            "published": (ex_.get("dcat_issued") or d["metadata_created"])[:10],
            "added_to_portal": d["metadata_created"][:10],
            "modified": d["metadata_modified"][:10],
            "harvest_source": ex_.get("harvest_source_title", ""),
            "harvested_from": harvested_from,
            "twin_id": tw[1] if tw else "",
            "twin_match": how,
            "twin_in_water_group": int(in_water(rec[tw])) if tw else "",
            "num_resources": d.get("num_resources", 0),
            "views_total": u[0],
            "views_recent_14d": u[1],
            "resource_views_total": u[2],
            "url": f"{PORTALS[p]}/dataset/{d['name']}",
        })

    with open("data/water_datasets.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    meta = {
        "fetched": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "records": len(out),
        "water_group_counts": {pp: sum(1 for r in out if r["portal"] == pp and r["in_water_group"]) for pp in ("data.ca.gov", "data.cnra.ca.gov")},
        "tracking_failures": sum(1 for k in keys if usage.get(k) is None),
    }
    json.dump(meta, open("data/water_datasets_meta.json", "w"), indent=2)
    print(json.dumps(meta, indent=2), file=sys.stderr)


if __name__ == "__main__":
    main()
