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
OWID_GRAPHER = ("https://ourworldindata.org/grapher/{}.csv"
                "?v=1&csvType=full&useColumnShortNames=false")

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


# ------------------------------------------------------------------ FAO gida
# FAOSTAT'in kendi API'si ARTIK ANAHTAR ISTIYOR:
#   faostatservices.fao.org -> HTTP 401 Unauthorized
#   fenixservices.fao.org   -> HTTP 521 (sunucu ayakta degil)
# (16 Eyl 2026'da Actions uzerinden olculdu.) Kanalin "sifir maliyet, sifir
# secret" modelini bozmamak icin ayni FAO verisini Our World in Data'nin
# anahtarsiz grapher CSV'lerinden aliyoruz. OWID bu seriyi dogrudan
# FAOSTAT'tan turetiyor, yani veri ayni; sadece tasiyici degisti.
#
# urun -> (OWID grapher slug, CSV'deki deger kolonu)
# Bu esmeler 16 Eyl 2026'da tek tek dogrulandi. Yeni urun eklemeden once
# slug'i gercekten kontrol et; yanlis slug sessiz bir konu kaybi demek.
FOOD_SERIES = {
    "coffee":  ("coffee-bean-production",  "Green coffee - Production (tonnes)"),
    "cocoa":   ("cocoa-bean-production",   "Cocoa beans - Production (tonnes)"),
    "wine":    ("wine-production",         "Wine - Production (tonnes)"),
    "rice":    ("rice-production",         "Rice - Production (tonnes)"),
    "wheat":   ("wheat-production",        "Wheat - Production (tonnes)"),
    "banana":  ("banana-production",       "Bananas - Production (tonnes)"),
    "potato":  ("potato-production",       "Potatoes - Production (tonnes)"),
    "tomato":  ("tomato-production",       "Tomatoes - Production (tonnes)"),
    "grape":   ("grapes-production",       "Grapes - Production (tonnes)"),
    "orange":  ("orange-production",       "Oranges - Production (tonnes)"),
    "apple":   ("apple-production",        "Apples - Production (tonnes)"),
    "sugar":   ("sugar-cane-production",   "Sugar cane - Production (tonnes)"),
    "maize":   ("maize-production",        "Maize (corn) - Production (tonnes)"),
    "soybean": ("soybean-production",      "Soybeans - Production (tonnes)"),
}
# Denenip BULUNAMAYAN urunler (OWID'de bu isimle grapher yok): tea, olive,
# honey, cattle, sheep, chicken. Eklemek istersen once slug'i dogrula.


def food_series(key, start, end):
    """{iso3: {yil: deger}}, {iso3: isim} — FAO uretim verisi (OWID uzerinden)."""
    if key not in FOOD_SERIES:
        raise ValueError(f"bilinmeyen urun: {key}")
    slug, column = FOOD_SERIES[key]
    blob = _cached(f"owid_{slug}.csv", lambda: _get(OWID_GRAPHER.format(slug)))
    text = blob.decode("utf-8", errors="replace").splitlines()

    series, names = {}, {}
    for row in csv.DictReader(text):
        iso = (row.get("Code") or "").strip()
        # OWID kita/gelir gruplarini da ayni dosyada veriyor; onlarin Code'u ya
        # bos ya da OWID_ ile basliyor. Gercek ulke disinda hicbir sey girmesin.
        if len(iso) != 3 or iso.startswith("OWID"):
            continue
        raw = (row.get(column) or "").strip()
        if not raw:
            continue
        try:
            year = int(row["Year"])
            val = float(raw)
        except (TypeError, ValueError, KeyError):
            continue
        if start <= year <= end and val > 0:
            series.setdefault(iso, {})[year] = val
            names[iso] = row.get("Entity") or iso

    if not series:
        raise RuntimeError(
            f"'{key}' ({slug}) icin ISO3 satiri bulunamadi — "
            f"slug veya '{column}' kolon adi degismis olabilir")
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
        series, names = food_series(topic["indicator"], start, end)
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
