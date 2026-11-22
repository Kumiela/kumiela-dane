#!/usr/bin/env python3
"""Zbieracz danych o Kumieli (Elbląg).

Co 15 minut (GitHub Actions) pobiera:
  - Hydrowskaz Miasta Elbląg (wszystkie stacje, surowe dane ze strony),
  - IMGW-PIB: 4 wodowskazy (rzeka Elbląg, Drużno, Zalew) i stację meteo Elbląg.
Zapisuje:
  dane/hydrowskaz.json            – ostatni odczyt Hydrowskazu (czyta go strona o Kumieli)
  dane/imgw.json                  – ostatni odczyt IMGW
  archiwum/hydrowskaz/RRRR-MM-DD.jsonl – każdy NOWY stan Hydrowskazu (jedna linia = jeden odczyt)
  archiwum/imgw/RRRR-MM.csv       – pomiary IMGW bez powtórzeń
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
    # archiwum: tylko gdy stan się zmienił
    digest = hashlib.sha256(json.dumps(stations, sort_keys=True).encode()).hexdigest()
    shafile = "dane/hydrowskaz.sha256"
    old = open(shafile).read().strip() if os.path.exists(shafile) else ""
    if digest != old:
        day = NOW.strftime("%Y-%m-%d")
        os.makedirs("archiwum/hydrowskaz", exist_ok=True)
        with open(f"archiwum/hydrowskaz/{day}.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"pobrano": LOG["pobrano"], "Stations": stations}, ensure_ascii=False) + "\n")
        with open(shafile, "w") as f:
            f.write(digest)
        return f"ok, {len(stations)} stacji, nowy stan zapisany"
    return f"ok, {len(stations)} stacji, bez zmian"


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
