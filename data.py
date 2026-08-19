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
    if topic["source"] == "worldbank":
        meta = wb_countries()
        names   = {i: v[0] for i, v in meta.items()}
        regions = {i: v[1] for i, v in meta.items()}
        series = wb_series(topic["indicator"], start, end)
    elif topic["source"] == "owid":
        series, names = owid_series(topic["indicator"], start, end)
        wb = wb_countries()
        regions = {i: v[1] for i, v in wb.items()}
    else:
        raise ValueError(f"bilinmeyen kaynak: {topic['source']}")

    return build_race(series, names, regions, topic.get("scope", "world"),
                      start, end, top_n=int(topic.get("top_n", 12)))
