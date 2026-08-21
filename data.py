#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EveryYearCounts — data.py
Kaynaklar:
  worldbank : https://api.worldbank.org/v2  (anahtar gerekmiyor)
  owid      : raw.githubusercontent.com/owid/co2-data (CSV)
Her indirme cache/ altina yazilir; ayni konu tekrar render edilirse ag'a cikilmaz.
"""
import csv
import json
import os
import time
import urllib.request

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
os.makedirs(CACHE, exist_ok=True)

WB_BASE   = "https://api.worldbank.org/v2"
FAO_BASE  = "https://faostatservices.fao.org/api/v1/en/data"
OWID_CO2  = "https://raw.githubusercontent.com/owid/co2-data/master/owid-co2-data.csv"

# World Bank'in ulke listesinde bolge/gelir grubu toplamlari da var; bunlari eleriz
AGGREGATE_REGION_ID = "NA"

# Kapsam tanimlari — topics.yaml bunlari isimle cagirir
SCOPES = {
    "world":        None,   # tum ulkeler
    "europe":       {"ECS"},
    "asia":         {"EAS", "SAS"},
    "africa":       {"SSF", "MEA"},
    "americas":     {"LCN", "NAC"},
    "middle_east":  {"MEA"},
}


# ------------------------------------------------------------------ yardimci
def _get(url, retries=4, timeout=45):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "EveryYearCounts/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as exc:                       # gecici ag hatasi
            last = exc
            time.sleep(2 ** i)
    raise RuntimeError(f"fetch failed: {url} ({last})")


def _cached(name, loader):
    path = os.path.join(CACHE, name)
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 30 * 86400:
        with open(path, "rb") as f:
            return f.read()
    blob = loader()
    with open(path, "wb") as f:
        f.write(blob)
    return blob


# ------------------------------------------------------------------ World Bank
def wb_countries():
    """{iso3: (isim, bolge_id)} — sadece gercek ulkeler."""
    blob = _cached("wb_countries.json",
                   lambda: _get(f"{WB_BASE}/country?format=json&per_page=400"))
    payload = json.loads(blob)
    out = {}
    for c in payload[1]:
        region = (c.get("region") or {}).get("id")
        if not region or region == AGGREGATE_REGION_ID:
            continue                                    # toplam/bolge satiri
        out[c["id"]] = (c["name"], region)
    return out


def wb_series(indicator, start, end):
    """{iso3: {yil: deger}}"""
    fname = f"wb_{indicator}_{start}_{end}.json"
    url = (f"{WB_BASE}/country/all/indicator/{indicator}"
           f"?format=json&per_page=20000&date={start}:{end}")
    payload = json.loads(_cached(fname, lambda: _get(url)))
    if len(payload) < 2 or not payload[1]:
        raise RuntimeError(f"no data for {indicator}")
    series = {}
    for row in payload[1]:
        if row["value"] is None:
            continue
        iso = row.get("countryiso3code") or ""
        if len(iso) != 3:
            continue
        series.setdefault(iso, {})[int(row["date"])] = float(row["value"])
    return series


# ------------------------------------------------------------------ OWID
def owid_series(column, start, end):
    """{iso3: {yil: deger}} — OWID CO2 veri setindeki herhangi bir kolon."""
    blob = _cached("owid_co2.csv", lambda: _get(OWID_CO2))
    text = blob.decode("utf-8", errors="replace").splitlines()
    series, names = {}, {}
    for row in csv.DictReader(text):
        iso = (row.get("iso_code") or "").strip()
        if len(iso) != 3 or iso.startswith("OWID"):
            continue                                    # toplam satirlari
        raw = row.get(column, "")
        if not raw:
            continue
        try:
            year = int(row["year"])
            val = float(raw)
        except ValueError:
            continue
        if start <= year <= end:
            series.setdefault(iso, {})[year] = val
            names[iso] = row["country"]
    return series, names


# ------------------------------------------------------------------ FAOSTAT
# FAO urun kodlari (domain QCL = Crops and Livestock Products)
# element 5510 = uretim (ton), 5111 = canli hayvan sayisi (bas)
FAO_ITEMS = {
    "coffee":  (656,  5510), "cocoa":   (661,  5510), "tea":     (667,  5510),
    "wine":    (564,  5510), "rice":    (27,   5510), "wheat":   (15,   5510),
    "banana":  (486,  5510), "olive":   (260,  5510), "honey":   (1182, 5510),
    "potato":  (116,  5510), "tomato":  (388,  5510), "grape":   (560,  5510),
    "orange":  (490,  5510), "apple":   (515,  5510), "sugar":   (156,  5510),
    "cattle":  (866,  5111), "sheep":   (976,  5111), "chicken": (1057, 5111),
}


def faostat_series(key, start, end):
    """{iso3: {yil: deger}}, {iso3: isim} — FAOSTAT uretim/stok verisi."""
    if key not in FAO_ITEMS:
        raise ValueError(f"bilinmeyen FAO urunu: {key}")
    item, element = FAO_ITEMS[key]
    fname = f"fao_{key}_{start}_{end}.json"
    url = (f"{FAO_BASE}/QCL?area=all&item={item}&element={element}"
           f"&year_range={start}:{end}&area_cs=ISO3&show_codes=true"
           f"&show_unit=false&show_flags=false&null_values=false&output_type=objects")
    payload = json.loads(_cached(fname, lambda: _get(url)))
    rows = payload.get("data") or []
    if not rows:
        raise RuntimeError(f"FAOSTAT '{key}' icin veri donmedi")

    series, names = {}, {}
    for r in rows:
        iso = str(r.get("Area Code (ISO3)") or r.get("Area Code") or "").strip()
        if len(iso) != 3 or not iso.isalpha():
            continue
        try:
            year = int(r.get("Year"))
            val = float(str(r.get("Value")).replace(",", ""))
        except (TypeError, ValueError):
            continue
        if start <= year <= end and val > 0:
            series.setdefault(iso, {})[year] = val
            names[iso] = r.get("Area") or iso
    if not series:
        raise RuntimeError(f"FAOSTAT '{key}': satir var ama ISO3 eslesmedi")
    return series, names


# ------------------------------------------------------------------ hazirlama
def build_race(series, names, regions, scope, start, end,
               top_n=12, min_coverage=0.85):
    """
    Ham seriyi renderer'in bekledigi hale getirir:
      - kapsama gore filtre
      - eksik yillari komsu yillardan doldur, kapsamasi dusuk ulkeyi at
      - son yila gore ilk top_n ulkeyi sec
    Donus: (raw {isim: [deger...]}, years [..])
    """
    years = list(range(start, end + 1))
    allowed = SCOPES.get(scope)
    ok = {}
    for iso, by_year in series.items():
        # KRITIK: WLD (Dunya), OED (OECD), IBT (IBRD+IDA), EUU (AB) gibi toplam
        # satirlari gercek ulke degil. names sadece gercek ulkeleri icerir;
        # listede olmayan her kod elenir.
        if iso not in names:
            continue
        if allowed is not None:
            reg = regions.get(iso)
            if reg not in allowed:
                continue
        have = [y for y in years if y in by_year]
        if len(have) < min_coverage * len(years):
            continue                                    # veri deligi cok
        filled, last = [], None
        for y in years:
            v = by_year.get(y)
            if v is None:
                v = last if last is not None else by_year[have[0]]
            filled.append(v)
            last = v
        ok[iso] = filled

    if len(ok) < 5:
        raise RuntimeError(f"scope '{scope}' icin yeterli ulke yok ({len(ok)})")

    ranked = sorted(ok, key=lambda i: ok[i][-1], reverse=True)[:top_n]
    raw = {names.get(i, i): ok[i] for i in ranked}
    return raw, years


def load_topic(topic):
    """topics.yaml'daki tek bir konu kaydini veriye cevirir."""
    start, end = int(topic["start"]), int(topic["end"])
    scope = topic.get("scope", "world")

    if topic["source"] == "worldbank":
        meta = wb_countries()
        names   = {i: v[0] for i, v in meta.items()}
        regions = {i: v[1] for i, v in meta.items()}
        series = wb_series(topic["indicator"], start, end)

    elif topic["source"] == "faostat":
        series, names = faostat_series(topic["indicator"], start, end)
        regions = {}
        if scope != "world":
            regions = {i: v[1] for i, v in wb_countries().items()}

    elif topic["source"] == "owid":
        series, names = owid_series(topic["indicator"], start, end)
        # Bolge bilgisi sadece dar kapsamda gerekli; 'world' icin World Bank'e
        # hic cikma (OWID konusu WB kesintisinde patlamasin).
        regions = {}
        if scope != "world":
            regions = {i: v[1] for i, v in wb_countries().items()}

    else:
        raise ValueError(f"bilinmeyen kaynak: {topic['source']}")

    return build_race(series, names, regions, scope,
                      start, end, top_n=int(topic.get("top_n", 12)))
