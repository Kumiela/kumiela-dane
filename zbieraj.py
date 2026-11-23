#!/usr/bin/env python3
"""Zbieracz danych o Kumieli (Elbląg).

Co 15 minut (GitHub Actions) pobiera:
  - Hydrowskaz Miasta Elbląg (wszystkie stacje, surowe dane ze strony),
  - IMGW-PIB: 4 wodowskazy (rzeka Elbląg, Drużno, Zalew) i stację meteo Elbląg.
Zapisuje:
  dane/hydrowskaz.json            – ostatni odczyt Hydrowskazu (czyta go strona o Kumieli)
  dane/imgw.json                  – ostatni odczyt IMGW
  archiwum/hydrowskaz/RRRR-MM.csv – pomiary wszystkich czujników Hydrowskazu bez powtórzeń
  archiwum/imgw/RRRR-MM.csv       – pomiary IMGW bez powtórzeń
  dane/opad_hydrowskaz.json      – opad 1/3/6/24 h przy Goplanicy (127) i Drużnie (138), z licznika
  dane/log.json                   – co się udało w ostatnim przebiegu
Źródła danych: IMGW-PIB (dane publiczne), Hydrowskaz Miasta Elbląg.
"""
import csv, datetime, hashlib, json, os, re, urllib.request

UA = {"User-Agent": "kumiela-archiwum/1.0 (strona krajoznawcza o rzece Kumiela; odczyt co 15 min)"}
NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
LOG = {"pobrano": NOW.isoformat().replace("+00:00", "Z"), "zrodla": {}}

HYDRO_IMGW = {"154190060": "Elbląg (rz. Elbląg)", "154190080": "Żukowo (jez. Drużno)",
              "154190050": "Nowe Batorowo (Zalew)", "154190090": "Tolkmicko (Zalew)"}
METEO_IMGW = "254190190"  # Elbląg, stacja telemetryczna


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def extract_js_object(html, var_name):
    """Wyciąga literał {...} przypisany do zmiennej JS, z dopasowaniem nawiasów."""
    m = re.search(r"var\s+" + re.escape(var_name) + r"\s*=\s*", html)
    if not m:
        raise ValueError("brak zmiennej " + var_name)
    j = html.index("{", m.end())
    depth, in_str, quote, esc = 0, False, "", False
    for k in range(j, len(html)):
        c = html[k]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == quote:
                in_str = False
        elif c in "\"'":
            in_str, quote = True, c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return html[j:k + 1]
    raise ValueError("niedomknięty obiekt " + var_name)


# ---------- Hydrowskaz ----------
def hydrowskaz():
    html = get("https://elblag.hydrowskaz.pl/")
    raw = extract_js_object(html, "Stations")
    try:
        stations = json.loads(raw)
    except json.JSONDecodeError as e:
        os.makedirs("dane", exist_ok=True)
        with open("dane/hydrowskaz_blad.txt", "w", encoding="utf-8") as f:
            f.write(str(e) + "\n\n" + raw[:6000])
        raise
    latest = {"pobrano": LOG["pobrano"], "zrodlo": "https://elblag.hydrowskaz.pl/", "Stations": stations}
    save_json("dane/hydrowskaz.json", latest)
    if os.path.exists("dane/hydrowskaz_blad.txt"):
        os.remove("dane/hydrowskaz_blad.txt")
    # archiwum: zwarty CSV, jeden wiersz = jeden pomiar jednego czujnika, bez powtórzeń
    from zoneinfo import ZoneInfo
    waw = ZoneInfo("Europe/Warsaw")
    rows = []
    for key, st in stations.items():
        if not isinstance(st, dict):
            continue
        for s in st.get("sensory") or []:
            if s.get("value") is None or not s.get("czas"):
                continue
            try:
                t = datetime.datetime.strptime(s["czas"], "%Y-%m-%d %H:%M").replace(tzinfo=waw)
                t = t.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
            except ValueError:
                continue
            rows.append([t, key, st.get("stacja", ""), s.get("czujnik", ""), s["value"], s.get("jednostka", "")])
    path = "archiwum/hydrowskaz/" + NOW.strftime("%Y-%m") + ".csv"
    os.makedirs("archiwum/hydrowskaz", exist_ok=True)
    seen = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for r in csv.reader(f):
                seen.add((r[0], r[1], r[3]) if len(r) > 3 else tuple(r))
    new = [r for r in rows if (r[0], str(r[1]), r[3]) not in seen]
    header = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if header:
            w.writerow(["czas_utc", "stacja_id", "stacja", "czujnik", "wartosc", "jednostka"])
        w.writerows(new)
    opad_z_licznika(now_rows=rows)
    return f"ok, {len(rows)} odczytów czujników, {len(new)} nowych w archiwum"


def opad_z_licznika(now_rows):
    """Hydrowskaz podaje „Suma opadu” jako licznik narastający. Liczy opad za 1, 6 i 24 h
    z różnic odczytów w archiwum (bieżący i poprzedni miesiąc). Zapis: dane/opad_hydrowskaz.json"""
    first = NOW.replace(day=1)
    prev = (first - datetime.timedelta(days=1)).strftime("%Y-%m")
    series = {}
    for m in (prev, NOW.strftime("%Y-%m")):
        path = f"archiwum/hydrowskaz/{m}.csv"
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("czujnik", "").startswith("Suma opadu"):
                    try:
                        t = datetime.datetime.strptime(r["czas_utc"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=datetime.timezone.utc)
                        series.setdefault(r["stacja_id"], {})[t] = float(r["wartosc"])
                    except (ValueError, KeyError):
                        pass
    out = {"pobrano": LOG["pobrano"], "uwaga": "opad liczony z różnic licznika „Suma opadu” Hydrowskazu; null = za mało danych albo licznik wyzerowany"}
    for sid, pts in series.items():
        ts = sorted(pts)
        last_t, last_v = ts[-1], pts[ts[-1]]
        st = {"czas": last_t.strftime("%Y-%m-%dT%H:%MZ"), "licznik_mm": last_v}
        for h in (1, 3, 6, 24):
            start = last_t - datetime.timedelta(hours=h)
            before = [t for t in ts if t <= start]
            if not before or (start - before[-1]) > datetime.timedelta(minutes=30):
                st[f"opad_{h}h"] = None
                continue
            d = last_v - pts[before[-1]]
            st[f"opad_{h}h"] = round(d, 2) if d >= 0 else None
        out[sid] = st
    save_json("dane/opad_hydrowskaz.json", out)


# ---------- IMGW ----------
def utc(s):
    """'2026-11-22 22:30:00' (IMGW, UTC) lub ISO -> ISO z Z."""
    if not s:
        return ""
    s = str(s).replace(" ", "T")
    if s.endswith("Z") or "+" in s[10:]:
        return s.replace("+00:00", "Z")
    return s + "Z"


def imgw():
    rows, latest, errors = [], {"pobrano": LOG["pobrano"], "hydro": {}, "meteo": {}}, []
    for sid, name in HYDRO_IMGW.items():
        try:
            d = json.loads(get(f"https://hydro-back.imgw.pl/station/hydro/status?id={sid}"))
            st = d["status"] if isinstance(d.get("status"), dict) else d
            cur = st.get("currentState") or {}
            if cur.get("value") is not None:
                rows.append([utc(cur.get("date")), "imgw", sid, "stan_wody", cur["value"], "cm"])
                latest["hydro"][sid] = {"nazwa": name, "czas": utc(cur.get("date")), "stan_cm": cur["value"],
                                        "ostrz": st.get("warningValue"), "alarm": st.get("alarmValue")}
        except Exception as e:
            errors.append(f"hydro {sid}: {e}")
    try:
        d = json.loads(get(f"https://hydro-back.imgw.pl/station/meteo/status?id={METEO_IMGW}"))
        st = d["status"] if isinstance(d.get("status"), dict) else d
        p = st.get("precip") or {}
        t = utc(p.get("date"))
        for key, label in [("precip3HoursSum", "opad_3h"), ("precip6HoursSum", "opad_6h"),
                           ("precip12HoursSum", "opad_12h"), ("precip24HoursSum", "opad_24h")]:
            if st.get(key) is not None:
                rows.append([t, "imgw", METEO_IMGW, label, st[key], "mm"])
                latest["meteo"][label] = st[key]
        if p.get("value") is not None:
            rows.append([t, "imgw", METEO_IMGW, "opad_1h", p["value"], "mm"])
            latest["meteo"]["opad_1h"] = p["value"]
        pd = st.get("precipDaily") or {}
        if pd.get("value") is not None:
            rows.append([utc(pd.get("date")), "imgw", METEO_IMGW, "opad_doba_do_6utc", pd["value"], "mm"])
        latest["meteo"]["opad_czas"] = t
    except Exception as e:
        errors.append(f"meteo opad: {e}")
    try:
        arr = json.loads(get(f"https://danepubliczne.imgw.pl/api/data/meteo/id/{METEO_IMGW}"))
        m = arr[0] if isinstance(arr, list) else arr
        for key, label, unit in [("temperatura_powietrza", "temp_powietrza", "C"),
                                 ("temperatura_gruntu", "temp_gruntu", "C"),
                                 ("wiatr_srednia_predkosc", "wiatr_sredni", "m/s"),
                                 ("wiatr_predkosc_maksymalna", "wiatr_max", "m/s"),
                                 ("wiatr_kierunek", "wiatr_kierunek", "deg"),
                                 ("wilgotnosc_wzgledna", "wilgotnosc", "%"),
                                 ("opad_10min", "opad_10min", "mm")]:
            if m.get(key) is not None:
                rows.append([utc(m.get(key + "_data")), "imgw", METEO_IMGW, label, m[key], unit])
                latest["meteo"][label] = m[key]
                latest["meteo"][label + "_czas"] = utc(m.get(key + "_data"))
    except Exception as e:
        errors.append(f"meteo telemetria: {e}")

    save_json("dane/imgw.json", latest)
    month = NOW.strftime("%Y-%m")
    path = f"archiwum/imgw/{month}.csv"
    os.makedirs("archiwum/imgw", exist_ok=True)
    seen = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for r in csv.reader(f):
                seen.add(tuple(r[:4]))
    new = [r for r in rows if r[0] and tuple(map(str, r[:4])) not in seen]
    write_header = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["czas_utc", "zrodlo", "stacja", "wielkosc", "wartosc", "jednostka"])
        w.writerows(new)
    msg = f"{len(new)} nowych pomiarów"
    if errors:
        msg += "; błędy: " + " | ".join(errors)
    return msg


for name, fn in [("hydrowskaz", hydrowskaz), ("imgw", imgw)]:
    try:
        LOG["zrodla"][name] = fn()
    except Exception as e:
        LOG["zrodla"][name] = f"BŁĄD: {type(e).__name__}: {e}"

save_json("dane/log.json", LOG)
print(json.dumps(LOG, ensure_ascii=False, indent=1))
