#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EveryYearCounts — topics.py
Gosterge x kapsam carpimi ile konu kuyrugunu uretir -> topics.yaml
Bir kere calistirilir, ciktisi repoya girer. Sonra elle satir eklenip cikarilabilir.
"""
import itertools
import yaml

# ---------------------------------------------------------------- gostergeler
# (kod, kaynak, baslik sablonu, birim, tema, baslangic yili)
INDICATORS = [
    # --- Nufus & toplum
    ("SP.POP.TOTL",        "worldbank", "Population",                    "",     "society", 1960),
    ("SP.URB.TOTL",        "worldbank", "Urban Population",              "",     "society", 1960),
    ("SP.DYN.LE00.IN",     "worldbank", "Life Expectancy",               " yrs", "society", 1960),
    ("SP.DYN.TFRT.IN",     "worldbank", "Fertility Rate",                "",     "society", 1960),
    ("SP.POP.65UP.TO.ZS",  "worldbank", "Share of Population Over 65",   "%",    "society", 1960),
    ("SE.ADT.LITR.ZS",     "worldbank", "Literacy Rate",                 "%",    "society", 1980),

    # --- Ekonomi
    ("NY.GDP.MKTP.CD",     "worldbank", "GDP",                           " $",   "economy", 1960),
    ("NY.GDP.PCAP.CD",     "worldbank", "GDP per Capita",                " $",   "economy", 1960),
    ("NE.EXP.GNFS.CD",     "worldbank", "Exports",                       " $",   "economy", 1960),
    ("NE.IMP.GNFS.CD",     "worldbank", "Imports",                       " $",   "economy", 1960),
    ("FP.CPI.TOTL.ZG",     "worldbank", "Inflation Rate",                "%",    "economy", 1970),
    ("SL.UEM.TOTL.ZS",     "worldbank", "Unemployment Rate",             "%",    "economy", 1991),
    ("BX.KLT.DINV.CD.WD",  "worldbank", "Foreign Direct Investment",     " $",   "economy", 1970),
    ("GC.DOD.TOTL.GD.ZS",  "worldbank", "Government Debt (% of GDP)",    "%",    "economy", 1990),

    # --- Enerji & cevre
    ("co2",                "owid",      "CO2 Emissions",                 " Mt",  "energy",  1960),
    ("co2_per_capita",     "owid",      "CO2 Emissions per Person",      " t",   "energy",  1960),
    ("coal_co2",           "owid",      "CO2 from Coal",                 " Mt",  "energy",  1960),
    ("oil_co2",            "owid",      "CO2 from Oil",                  " Mt",  "energy",  1960),
    ("gas_co2",            "owid",      "CO2 from Gas",                  " Mt",  "energy",  1960),
    ("cumulative_co2",     "owid",      "Cumulative CO2 Emissions",      " Mt",  "energy",  1960),
    ("EG.USE.ELEC.KH.PC",  "worldbank", "Electricity Use per Person",    " kWh", "energy",  1971),
    ("AG.LND.FRST.K2",     "worldbank", "Forest Area",                   " km2", "energy",  1990),

    # --- Teknoloji
    ("IT.NET.USER.ZS",     "worldbank", "Internet Users",                "%",    "tech",    1990),
    ("IT.CEL.SETS.P2",     "worldbank", "Mobile Subscriptions per 100",  "",     "tech",    1980),
    ("GB.XPD.RSDV.GD.ZS",  "worldbank", "R&D Spending (% of GDP)",       "%",    "tech",    1996),

    # --- Devlet & altyapi
    ("MS.MIL.XPND.CD",     "worldbank", "Military Spending",             " $",   "power",   1960),
    ("MS.MIL.TOTL.P1",     "worldbank", "Armed Forces Personnel",        "",     "power",   1985),
    ("ST.INT.ARVL",        "worldbank", "International Tourist Arrivals", "",    "power",   1995),
    ("SH.XPD.CHEX.GD.ZS",  "worldbank", "Health Spending (% of GDP)",    "%",    "society", 2000),
]

SCOPE_LABEL = {
    "world":       "the World",
    "europe":      "Europe",
    "asia":        "Asia",
    "africa":      "Africa & Middle East",
    "americas":    "the Americas",
    "middle_east": "the Middle East",
}

# Yuzde/oran gostergeleri kucuk kapsamda anlamsizlasabilir; sadece genis kapsam
WORLD_ONLY = {"FP.CPI.TOTL.ZG", "GC.DOD.TOTL.GD.ZS", "GB.XPD.RSDV.GD.ZS"}

END_YEAR = 2024


def make_topics():
    topics = []
    for (code, source, label, unit, theme, start) in INDICATORS:
        scopes = ["world"] if code in WORLD_ONLY else list(SCOPE_LABEL)
        for scope in scopes:
            slug = f"{code.replace('.', '_').lower()}__{scope}"
            topics.append({
                "id": slug,
                "source": source,
                "indicator": code,
                "scope": scope,
                "start": start,
                "end": END_YEAR,
                "top_n": 12,
                "theme": theme,
                "unit": unit,
                "title": f"Top 10 Countries by {label} in {SCOPE_LABEL[scope]}",
                "chart_title": f"{label} — {SCOPE_LABEL[scope].title()}",
                "source_label": ("World Bank" if source == "worldbank"
                                 else "Our World in Data"),
            })
    return topics


def main():
    topics = make_topics()
    with open("topics.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump({"topics": topics}, f, sort_keys=False, allow_unicode=True)
    themes = {}
    for t in topics:
        themes[t["theme"]] = themes.get(t["theme"], 0) + 1
    print(f"{len(topics)} konu yazildi -> topics.yaml")
    for k, v in sorted(themes.items()):
        print(f"  {k:10s} {v}")


if __name__ == "__main__":
    main()
