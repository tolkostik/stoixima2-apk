"""
Βελτιώσεις ανάλυσης:
  • Αποτελέσματα αγώνων (football-data.co.uk, ESPN) για αυτόματο έλεγχο δελτίων.
  • Στατιστικό μοντέλο Poisson από τα γκολ της σεζόν: «δεύτερη γνώμη» δίπλα στην αγορά.
  • Δείκτης αξιοπιστίας ανά αγώνα (μέγεθος πρωταθλήματος, ποιότητα αποδόσεων, συμφωνία μοντέλου).
  • Ιστορικό δελτίων, στατιστικά επιτυχίας, διαχείριση κεφαλαίου.
"""
import csv
import datetime
import io
import json
import math
import time

import betting as B

FD = "https://www.football-data.co.uk"
NEW_LEAGUE_FILES = {"Argentina": "ARG", "Austria": "AUT", "Brazil": "BRA", "China": "CHN", "Denmark": "DNK",
                    "Finland": "FIN", "Ireland": "IRL", "Japan": "JPN", "Mexico": "MEX", "Norway": "NOR",
                    "Poland": "POL", "Romania": "ROU", "Russia": "RUS", "Sweden": "SWE", "Switzerland": "SWZ",
                    "USA": "USA"}
TIER1 = {"E0", "SP1", "I1", "D1", "F1"}
TIER2 = {"E1", "N1", "P1", "B1", "T1", "SC0", "D2", "I2", "SP2", "F2", "G1"}


# ------------------------------------------------------------------ αποτελέσματα ποδοσφαίρου
def season_code(d=None):
    d = d or datetime.date.today()
    y = d.year if d.month >= 7 else d.year - 1
    return f"{y % 100:02d}{(y + 1) % 100:02d}"


def _prev_season(code):
    y = int(code[:2]) - 1
    return f"{y % 100:02d}{(y + 1) % 100:02d}"


def result_url(m, season=None):
    if m.get("div") and m["div"] in B.LEAGUES:
        return f"{FD}/mmz4281/{season or season_code()}/{m['div']}.csv"
    code = NEW_LEAGUE_FILES.get(m.get("country", ""))
    return f"{FD}/new/{code}.csv" if code else None


def _date(s):
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.datetime.strptime(s.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def parse_results(raw):
    """[(ημερομηνία, γηπεδούχος, φιλοξενούμενος, γκολ γηπ., γκολ φιλ.)]"""
    out = []
    for row in csv.DictReader(io.StringIO(raw.decode("utf-8-sig", errors="replace"))):
        row = {(k or "").strip(): (v or "").strip() for k, v in row.items() if isinstance(v, str) or v is None}
        h = row.get("HomeTeam") or row.get("Home")
        a = row.get("AwayTeam") or row.get("Away")
        hg = row.get("FTHG") or row.get("HG")
        ag = row.get("FTAG") or row.get("AG")
        d = _date(row.get("Date", ""))
        if h and a and d and hg not in (None, "") and ag not in (None, ""):
            try:
                out.append((d, h, a, int(float(hg)), int(float(ag))))
            except ValueError:
                continue
    return out


_RES_CACHE = {}


def results_for(url, max_age=3 * 3600):
    hit = _RES_CACHE.get(url)
    if hit and time.time() - hit[0] < max_age:
        return hit[1]
    try:
        res = parse_results(B._get(url))
    except Exception:  # noqa: BLE001
        res = []
    _RES_CACHE[url] = (time.time(), res)
    return res


# ------------------------------------------------------------------ μοντέλο Poisson
def _pois(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def fit(results, days=400):
    """Δυνάμεις επίθεσης/άμυνας ανά ομάδα, με «συρρίκνωση» προς τον μέσο όρο για λίγα παιχνίδια."""
    if not results:
        return None
    last = max(r[0] for r in results)
    rs = [r for r in results if (last - r[0]).days <= days]
    if len(rs) < 30:
        return None
    hg = sum(r[3] for r in rs) / len(rs)
    ag = sum(r[4] for r in rs) / len(rs)
    st = {}
    for d, h, a, x, y in rs:
        w = 1.0 if (last - d).days <= 200 else 0.5          # πρόσφατα παιχνίδια μετράνε περισσότερο
        sh = st.setdefault(h, {"hs": 0.0, "hc": 0.0, "hn": 0.0, "as": 0.0, "ac": 0.0, "an": 0.0})
        sa = st.setdefault(a, {"hs": 0.0, "hc": 0.0, "hn": 0.0, "as": 0.0, "ac": 0.0, "an": 0.0})
        sh["hs"] += w * x
        sh["hc"] += w * y
        sh["hn"] += w
        sa["as"] += w * y
        sa["ac"] += w * x
        sa["an"] += w
    teams = {}
    k = 4.0
    for t, v in st.items():
        def strength(goals, n, avg):
            raw = (goals / n) / avg if n and avg else 1.0
            return (raw * n + 1.0 * k) / (n + k)
        teams[t] = {"ha": strength(v["hs"], v["hn"], hg), "hd": strength(v["hc"], v["hn"], ag),
                    "aa": strength(v["as"], v["an"], ag), "ad": strength(v["ac"], v["an"], hg),
                    "n": v["hn"] + v["an"]}
    return {"hg": hg, "ag": ag, "teams": teams}


def predict(params, home, away):
    if not params:
        return None
    t = params["teams"]
    if home not in t or away not in t or t[home]["n"] < 3 or t[away]["n"] < 3:
        return None
    lh = t[home]["ha"] * t[away]["ad"] * params["hg"]
    la = t[away]["aa"] * t[home]["hd"] * params["ag"]
    p1 = px = p2 = over = 0.0
    for i in range(11):
        pi = _pois(i, lh)
        for j in range(11):
            pr = pi * _pois(j, la)
            if i > j:
                p1 += pr
            elif i == j:
                px += pr
            else:
                p2 += pr
            if i + j >= 3:
                over += pr
    tot = p1 + px + p2
    return {"1": p1 / tot, "Χ": px / tot, "2": p2 / tot, "1Χ": (p1 + px) / tot, "Χ2": (px + p2) / tot,
            "12": (p1 + p2) / tot, "Over 2,5": over, "Under 2,5": 1 - over, "xg": (lh, la)}


def build_models(matches, log=lambda s: None):
    """Μοντέλα ανά πρωτάθλημα για τους αγώνες που υπάρχουν (κρατιούνται στη μνήμη για τη συνεδρία)."""
    models = {}
    urls = {}
    for m in matches:
        if m["sport"] != "football":
            continue
        u = result_url(m)
        if u:
            urls.setdefault(u, m)
    for i, (u, m) in enumerate(urls.items(), 1):
        log(f"Μοντέλο {i}/{len(urls)}: {m['league']}…")
        res = list(results_for(u))
        if m.get("div") in B.LEAGUES:
            res += results_for(result_url(m, _prev_season(season_code())))
        models[u] = fit(res)
    return models


def model_prob(models, m, sign):
    if m["sport"] != "football":
        return None
    pr = predict(models.get(result_url(m)), m["home"], m["away"])
    return pr.get(sign) if pr else None


# ------------------------------------------------------------------ αξιοπιστία
def reliability(m, pick, model_p=None):
    """Δείκτης 0–100 και χαρακτηρισμός."""
    s = 50
    why = []
    if m["sport"] == "football":
        div = m.get("div", "")
        if div in TIER1:
            s += 25
            why.append("μεγάλο πρωτάθλημα")
        elif div in TIER2:
            s += 10
            why.append("μεσαίο πρωτάθλημα")
        elif div:
            why.append("μικρότερη κατηγορία")
        else:
            s -= 10
            why.append("πρωτάθλημα εκτός Ευρώπης/μικρή αγορά")
    else:
        if m["league"] == "NBA":
            s += 20
            why.append("NBA")
        elif m["league"].startswith("NCAA"):
            s -= 5
            why.append("κολεγιακό μπάσκετ")
    if m.get("pin"):
        s += 10
        why.append("αποδόσεις Pinnacle")
    mg = m.get("margin")
    if mg is not None:
        if mg < 0.035:
            s += 8
        elif mg > 0.07:
            s -= 8
            why.append("μεγάλο περιθώριο εταιρειών")
    if model_p is not None:
        diff = abs(model_p - pick["prob"])
        if diff <= 0.06:
            s += 12
            why.append("συμφωνεί το μοντέλο")
        elif diff > 0.12:
            s -= 15
            why.append("διαφωνεί το μοντέλο")
    s = max(0, min(100, s))
    label = "Υψηλή" if s >= 70 else ("Μέτρια" if s >= 45 else "Χαμηλή")
    return s, label, why


def is_greek(m):
    return m.get("div") == "G1" or m.get("country") == "Greece" or "Ελλάδα" in m.get("league", "")


# ------------------------------------------------------------------ ιστορικό δελτίων
def load_slips():
    return B._read("slips.json", [])


def save_slips(slips):
    B._write("slips.json", slips)


def add_slip(picks, stake, odds, kind="Κανονικό"):
    slips = load_slips()
    slips.insert(0, {"id": int(time.time() * 1000), "date": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
                     "kind": kind, "stake": round(float(stake), 2), "odds": round(float(odds), 2) if odds else None,
                     "status": "εκκρεμεί", "picks": picks})
    save_slips(slips)


def delete_slip(sid):
    save_slips([s for s in load_slips() if s["id"] != sid])


def pick_record(m, p, model_p=None, rel=None):
    return {"sport": m["sport"], "league": m["league"], "div": m.get("div", ""), "country": m.get("country", ""),
            "home": m["home"], "away": m["away"], "start": m["start"], "sign": p["sign"], "name": p["name"],
            "prob": round(p["prob"], 4), "fair_odds": round(p["fair_odds"], 3),
            "model": round(model_p, 4) if model_p is not None else None, "rel": rel, "result": None, "won": None}


def _won(sign, hg, ag, sport):
    if sport == "basketball":
        return (hg > ag) if sign == "1" else (ag > hg)
    return {"1": hg > ag, "Χ": hg == ag, "2": ag > hg, "1Χ": hg >= ag, "Χ2": ag >= hg, "12": hg != ag,
            "Over 2,5": hg + ag >= 3, "Under 2,5": hg + ag <= 2}.get(sign)


def _espn_result(pk):
    try:
        t = datetime.datetime.fromisoformat(pk["start"].replace("Z", "+00:00"))
    except ValueError:
        return None
    lg = {"NBA": "nba", "NCAA (ΗΠΑ)": "mens-college-basketball", "WNBA": "wnba"}.get(pk["league"])
    if not lg:
        return None
    for d in {t.strftime("%Y%m%d"), (t - datetime.timedelta(hours=8)).strftime("%Y%m%d")}:
        try:
            js = json.loads(B._get(B.ESPN.format(lg=lg, d=d)))
        except Exception:  # noqa: BLE001
            continue
        for ev in js.get("events", []):
            comp = (ev.get("competitions") or [{}])[0]
            if ((comp.get("status") or {}).get("type") or {}).get("state") != "post":
                continue
            sc = {c.get("homeAway"): ((c.get("team") or {}).get("displayName"), c.get("score"))
                  for c in comp.get("competitors", [])}
            if sc.get("home", (None,))[0] == pk["home"] and sc.get("away", (None,))[0] == pk["away"]:
                try:
                    return int(float(sc["home"][1])), int(float(sc["away"][1]))
                except (TypeError, ValueError):
                    return None
    return None


def _football_result(pk):
    u = result_url(pk)
    if not u:
        return None
    try:
        start = datetime.datetime.fromisoformat(pk["start"].replace("Z", "+00:00")).date()
    except ValueError:
        return None
    for d, h, a, x, y in results_for(u, max_age=1800):
        if h == pk["home"] and a == pk["away"] and abs((d - start).days) <= 2:
            return x, y
    return None


def settle_all(log=lambda s: None):
    """Ελέγχει τα αποτελέσματα των αγώνων που έχουν τελειώσει. Επιστρέφει πόσα σημεία ενημερώθηκαν."""
    slips = load_slips()
    now = datetime.datetime.now(datetime.timezone.utc)
    changed = 0
    for sl in slips:
        if sl["status"] != "εκκρεμεί":
            continue
        for pk in sl["picks"]:
            if pk.get("won") is not None:
                continue
            try:
                t = datetime.datetime.fromisoformat(pk["start"].replace("Z", "+00:00"))
            except ValueError:
                continue
            if now < t + datetime.timedelta(hours=2, minutes=30):
                continue
            log(f"Έλεγχος: {pk['home']} – {pk['away']}…")
            res = _espn_result(pk) if pk["sport"] == "basketball" else _football_result(pk)
            if res:
                pk["result"] = f"{res[0]}-{res[1]}"
                pk["won"] = bool(_won(pk["sign"], res[0], res[1], pk["sport"]))
                changed += 1
        if any(pk.get("won") is False for pk in sl["picks"]):
            sl["status"] = "χάθηκε"
        elif all(pk.get("won") is True for pk in sl["picks"]):
            sl["status"] = "κέρδισε"
    save_slips(slips)
    return changed


def stats():
    slips = load_slips()
    settled = [s for s in slips if s["status"] != "εκκρεμεί"]
    staked = sum(s["stake"] for s in settled)
    returned = sum(s["stake"] * (s["odds"] or 0) for s in settled if s["status"] == "κέρδισε")
    buckets = {}
    for s in slips:
        for pk in s["picks"]:
            if pk.get("won") is None:
                continue
            lo = min(90, int(pk["prob"] * 10) * 10)
            b = buckets.setdefault(lo, [0, 0, 0.0])
            b[0] += 1
            b[1] += 1 if pk["won"] else 0
            b[2] += pk["prob"]
    return {"slips": len(slips), "settled": len(settled),
            "won": sum(1 for s in settled if s["status"] == "κέρδισε"), "staked": staked,
            "profit": returned - staked, "buckets": dict(sorted(buckets.items()))}


# ------------------------------------------------------------------ διαχείριση κεφαλαίου
RISK = {"Συντηρητικό": (0.125, 0.01), "Μέτριο": (0.25, 0.02), "Επιθετικό": (0.5, 0.03)}


def bankroll_now(settings):
    return float(settings.get("bankroll", 100)) + stats()["profit"]


def week_spent():
    now = datetime.datetime.now()
    start = now - datetime.timedelta(days=now.weekday())
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    tot = 0.0
    for s in load_slips():
        try:
            d = datetime.datetime.strptime(s["date"], "%d/%m/%Y %H:%M")
        except ValueError:
            continue
        if d >= start:
            tot += s["stake"]
    return tot


def suggest_stake(settings, prob, offered_odds):
    """Πρόταση ποσού: κλασματικό Kelly όταν υπάρχει αξία, αλλιώς μικρό σταθερό ποσό για διασκέδαση."""
    bank = max(0.0, bankroll_now(settings))
    frac, flat = RISK.get(settings.get("risk", "Συντηρητικό"), RISK["Συντηρητικό"])
    limit = bank * float(settings.get("week_limit", 10)) / 100
    left = max(0.0, limit - week_spent())
    note = ""
    stake = 0.0
    if offered_odds and offered_odds > 1:
        edge = prob * offered_odds - 1
        if edge > 0:
            k = edge / (offered_odds - 1)
            stake = bank * k * frac
            note = f"Έχει αξία (+{edge * 100:.1f}%): πρόταση με κλασματικό Kelly.".replace(".", ",", 1)
        else:
            stake = bank * flat * 0.5
            note = (f"Χωρίς αξία ({edge * 100:.1f}%): μακροπρόθεσμα χάνεις. Αν το παίξεις, μόνο μικρό ποσό "
                    "για διασκέδαση.").replace(".", ",", 1)
    else:
        stake = bank * flat * 0.5
        note = "Γράψε τη συνολική απόδοση του ΟΠΑΠ για ακριβέστερη πρόταση."
    if stake > left:
        stake = left
        note += f" Περιορίστηκε από το όριο εβδομάδας (απομένουν {left:.2f} €).".replace(".", ",", 1)
    return max(0.0, round(stake * 2) / 2), note, left
