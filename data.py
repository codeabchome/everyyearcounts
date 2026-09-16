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

# ------------------------------------------------------------------ kapsamlar
# DIKKAT — World Bank BOLGE KODU ile filtrelemeyin. Kodlar cografi degil idari:
#   EAS = "East Asia & Pacific"        -> Avustralya, Yeni Zelanda, Fiji iceride
#   ECS = "Europe & Central Asia"      -> Kazakistan, Ozbekistan, Kirgizistan iceride
#   MEA = "Middle East & North Africa" -> Malta iceride
# Bu yuzden "Top 10 ... in Asia" videolarinda Avustralya, "in Europe"
# videolarinda Kazakistan cikiyordu; izleyicilerden gelen 1 numarali sikayet buydu.
# Artik kapsamlar elle dogrulanmis ISO3 listeleri. Yeni ulke eklerken listeye
# elle ekleyin; bolge koduna GERI DONMEYIN.
#
# Kita sinirindaki ulkeler (RUS, TUR, ARM, GEO, AZE, CYP) bilerek hem Avrupa'da
# hem Asya'da. Kazakistan bilerek SADECE Asya'da.

_EUROPE = {
    "ALB","AND","ARM","AUT","AZE","BEL","BGR","BIH","BLR","CHE","CHI","CYP",
    "CZE","DEU","DNK","ESP","EST","FIN","FRA","FRO","GBR","GEO","GIB","GRC",
    "HRV","HUN","IMN","IRL","ISL","ITA","LIE","LTU","LUX","LVA","MCO","MDA",
    "MKD","MLT","MNE","NLD","NOR","POL","PRT","ROU","RUS","SMR","SRB","SVK",
    "SVN","SWE","TUR","UKR","XKX",
}

_ASIA = {
    # Dogu Asya
    "CHN","HKG","JPN","KOR","MAC","MNG","PRK",
    # Guneydogu Asya
    "BRN","IDN","KHM","LAO","MMR","MYS","PHL","SGP","THA","TLS","VNM",
    # Guney Asya
    "AFG","BGD","BTN","IND","LKA","MDV","NPL","PAK",
    # Orta Asya
    "KAZ","KGZ","TJK","TKM","UZB",
    # Bati Asya / Ortadogu
    "ARE","ARM","AZE","BHR","CYP","GEO","IRN","IRQ","ISR","JOR","KWT","LBN",
    "OMN","PSE","QAT","SAU","SYR","TUR","YEM",
    # Avrasya
    "RUS",
}

_MIDDLE_EAST = {
    "ARE","BHR","EGY","IRN","IRQ","ISR","JOR","KWT","LBN","OMN","PSE","QAT",
    "SAU","SYR","TUR","YEM",
}

_AFRICA = {
    "AGO","BDI","BEN","BFA","BWA","CAF","CIV","CMR","COD","COG","COM","CPV",
    "DJI","DZA","EGY","ERI","ESH","ETH","GAB","GHA","GIN","GMB","GNB","GNQ",
    "KEN","LBR","LBY","LSO","MAR","MDG","MLI","MOZ","MRT","MUS","MWI","MYT",
    "NAM","NER","NGA","RWA","SDN","SEN","SLE","SOM","SSD","STP","SWZ","SYC",
    "TCD","TGO","TUN","TZA","UGA","ZAF","ZMB","ZWE",
}

_AMERICAS = {
    "ABW","ARG","ATG","BHS","BLZ","BMU","BOL","BRA","BRB","CAN","CHL","COL",
    "CRI","CUB","CUW","CYM","DMA","DOM","ECU","GRD","GTM","GUY","HND","HTI",
    "JAM","KNA","LCA","MEX","NIC","PAN","PER","PRI","PRY","SLV","SUR","SXM",
    "TCA","TTO","URY","USA","VCT","VEN","VGB","VIR",
}

# Kapsam tanimlari — topics.py bunlari isimle cagirir. None = tum ulkeler.
SCOPES = {
    "world":        None,
    "europe":       _EUROPE,
    "asia":         _ASIA,
    "africa":       _AFRICA,
    "americas":     _AMERICAS,
    "middle_east":  _MIDDLE_EAST,
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
def build_race(series, names, regions, scope, start, end,   # regions: kullanilmiyor
               top_n=12, min_coverage=0.85):
    """
    Ham seriyi renderer'in bekledigi hale getirir:
      - kapsama gore filtre (SCOPES'taki ISO3 listesine gore)
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
        if allowed is not None and iso not in allowed:
            continue                                    # kapsam disi ulke
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
        regions = {}   # kapsam artik ISO3 listesinden geliyor, WB'ye cikmiyoruz

    elif topic["source"] == "owid":
        series, names = owid_series(topic["indicator"], start, end)
        # Kapsam artik ISO3 listesinden geliyor; OWID konulari World Bank'e hic
        # cikmiyor (WB kesintisi OWID videosunu artik patlatamaz).
        regions = {}

    else:
        raise ValueError(f"bilinmeyen kaynak: {topic['source']}")

    return build_race(series, names, regions, scope,
                      start, end, top_n=int(topic.get("top_n", 12)))
