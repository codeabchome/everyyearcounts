#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EveryYearCounts - topics.py
Konu kuyrugunu MERAK SIRASINA gore uretir.

tier 1  - herkesin merak ettigi, arama hacmi yuksek (once bunlar)
tier 2  - guclu ama biraz daha nis
tier 3  - derinlik/cesitlilik (havuzu buyutur, tum kapsamlara acilir)

Ayni gosterge arka arkaya gelmesin diye kapsamlar serpistirilir.
"""
import yaml

END_YEAR = 2024

SCOPE_LABEL = {
    "world":       "the World",
    "europe":      "Europe",
    "asia":        "Asia",
    "africa":      "Africa & Middle East",
    "americas":    "the Americas",
    "middle_east": "the Middle East",
}

# (kod, kaynak, baslik, birim, tema, baslangic, tier, kapsamlar)
INDICATORS = [
    # ------------------------------------------------------------ TIER 1
    ("MS.MIL.XPND.CD",    "worldbank", "Military Spending",              " $",    "power",   1960, 1, ["world","europe","asia"]),
    ("NY.GDP.MKTP.CD",    "worldbank", "GDP",                            " $",    "economy", 1960, 1, ["world","europe","asia","africa"]),
    ("SP.POP.TOTL",       "worldbank", "Population",                     "",      "society", 1960, 1, ["world","africa","europe"]),
    ("NY.GDP.PCAP.CD",    "worldbank", "GDP per Capita",                 " $",    "economy", 1960, 1, ["world","europe","asia"]),
    ("FI.RES.TOTL.CD",    "worldbank", "Gold & Foreign Reserves",        " $",    "economy", 1960, 1, ["world","asia"]),
    ("VC.IHR.PSRC.P5",    "worldbank", "Homicide Rate",                  " /100k","society", 1990, 1, ["world","americas"]),
    ("SP.DYN.LE00.IN",    "worldbank", "Life Expectancy",                " yrs",  "society", 1960, 1, ["world","europe","africa"]),
    ("ST.INT.ARVL",       "worldbank", "Tourist Arrivals",               "",      "power",   1995, 1, ["world","europe"]),
    # [FAOSTAT devre disi - API formati calismadi, ayri turda duzeltilecek] ("coffee",            "faostat",   "Coffee Production",              " t",    "food",    1961, 1, ["world","americas"]),
    # [FAOSTAT devre disi - API formati calismadi, ayri turda duzeltilecek] ("cocoa",             "faostat",   "Cocoa Production",               " t",    "food",    1961, 1, ["world","africa"]),
    ("SH.ALC.PCAP.LI",    "worldbank", "Alcohol Consumption per Person", " L",    "society", 2000, 1, ["world","europe"]),

    # ------------------------------------------------------------ TIER 2
    ("IT.NET.USER.ZS",    "worldbank", "Internet Users",                 "%",     "tech",    1990, 2, ["world","africa","asia"]),
    ("co2",               "owid",      "CO2 Emissions",                  " Mt",   "energy",  1960, 2, ["world","asia","europe"]),
    ("NE.EXP.GNFS.CD",    "worldbank", "Exports",                        " $",    "economy", 1960, 2, ["world","asia","europe"]),
    ("SM.POP.TOTL",       "worldbank", "Immigrant Population",           "",      "society", 1990, 2, ["world","europe"]),
    ("BX.TRF.PWKR.CD.DT", "worldbank", "Money Sent Home by Migrants",    " $",    "economy", 1970, 2, ["world","asia"]),
    ("EG.FEC.RNEW.ZS",    "worldbank", "Renewable Energy Share",         "%",     "energy",  1990, 2, ["world","europe"]),
    ("SP.URB.TOTL",       "worldbank", "Urban Population",               "",      "society", 1960, 2, ["world","asia","africa"]),
    ("SL.UEM.TOTL.ZS",    "worldbank", "Unemployment Rate",              "%",     "economy", 1991, 2, ["world","europe"]),
    ("SH.XPD.CHEX.GD.ZS", "worldbank", "Health Spending",                "%",     "society", 2000, 2, ["world","europe"]),
    ("IT.CEL.SETS.P2",    "worldbank", "Mobile Phones per 100 People",   "",      "tech",    1980, 2, ["world","africa"]),
    ("EG.USE.ELEC.KH.PC", "worldbank", "Electricity Use per Person",     " kWh",  "energy",  1971, 2, ["world","asia"]),
    # [FAOSTAT devre disi - API formati calismadi, ayri turda duzeltilecek] ("tea",               "faostat",   "Tea Production",                 " t",    "food",    1961, 2, ["world","asia"]),
    # [FAOSTAT devre disi - API formati calismadi, ayri turda duzeltilecek] ("wine",              "faostat",   "Wine Production",                " t",    "food",    1961, 2, ["world","europe"]),
    # [FAOSTAT devre disi - API formati calismadi, ayri turda duzeltilecek] ("sugar",             "faostat",   "Sugar Production",               " t",    "food",    1961, 2, ["world","americas"]),

    # ------------------------------------------------------------ TIER 3
    ("FP.CPI.TOTL.ZG",    "worldbank", "Inflation Rate",                 "%",     "economy", 1970, 3, ["world"]),
    ("SP.DYN.TFRT.IN",    "worldbank", "Births per Woman",               "",      "society", 1960, 3, ["world"]),
    ("SE.ADT.LITR.ZS",    "worldbank", "Literacy Rate",                  "%",     "society", 1980, 3, ["world"]),
    ("NE.IMP.GNFS.CD",    "worldbank", "Imports",                        " $",    "economy", 1960, 3, ["world"]),
    ("BX.KLT.DINV.CD.WD", "worldbank", "Foreign Investment",             " $",    "economy", 1970, 3, ["world"]),
    ("AG.LND.FRST.K2",    "worldbank", "Forest Area",                    " km2",  "energy",  1990, 3, ["world"]),
    ("SP.POP.65UP.TO.ZS", "worldbank", "Share of People Over 65",        "%",     "society", 1960, 3, ["world"]),
    ("GB.XPD.RSDV.GD.ZS", "worldbank", "R&D Spending",                   "%",     "tech",    1996, 3, ["world"]),
    ("co2_per_capita",    "owid",      "CO2 per Person",                 " t",    "energy",  1960, 3, ["world"]),
    ("coal_co2",          "owid",      "CO2 from Coal",                  " Mt",   "energy",  1960, 3, ["world"]),
    ("oil_co2",           "owid",      "CO2 from Oil",                   " Mt",   "energy",  1960, 3, ["world"]),
    ("cumulative_co2",    "owid",      "Total CO2 Ever Emitted",         " Mt",   "energy",  1960, 3, ["world"]),
    # [FAOSTAT devre disi - API formati calismadi, ayri turda duzeltilecek] ("rice",              "faostat",   "Rice Production",                " t",    "food",    1961, 3, ["world"]),
    # [FAOSTAT devre disi - API formati calismadi, ayri turda duzeltilecek] ("wheat",             "faostat",   "Wheat Production",               " t",    "food",    1961, 3, ["world"]),
    # [FAOSTAT devre disi - API formati calismadi, ayri turda duzeltilecek] ("banana",            "faostat",   "Banana Production",              " t",    "food",    1961, 3, ["world"]),
    # [FAOSTAT devre disi - API formati calismadi, ayri turda duzeltilecek] ("olive",             "faostat",   "Olive Production",               " t",    "food",    1961, 3, ["world"]),
    # [FAOSTAT devre disi - API formati calismadi, ayri turda duzeltilecek] ("honey",             "faostat",   "Honey Production",               " t",    "food",    1961, 3, ["world"]),
    # [FAOSTAT devre disi - API formati calismadi, ayri turda duzeltilecek] ("potato",            "faostat",   "Potato Production",              " t",    "food",    1961, 3, ["world"]),
    # [FAOSTAT devre disi - API formati calismadi, ayri turda duzeltilecek] ("tomato",            "faostat",   "Tomato Production",              " t",    "food",    1961, 3, ["world"]),
    # [FAOSTAT devre disi - API formati calismadi, ayri turda duzeltilecek] ("grape",             "faostat",   "Grape Production",               " t",    "food",    1961, 3, ["world"]),
    # [FAOSTAT devre disi - API formati calismadi, ayri turda duzeltilecek] ("orange",            "faostat",   "Orange Production",              " t",    "food",    1961, 3, ["world"]),
    # [FAOSTAT devre disi - API formati calismadi, ayri turda duzeltilecek] ("apple",             "faostat",   "Apple Production",               " t",    "food",    1961, 3, ["world"]),
    # [FAOSTAT devre disi - API formati calismadi, ayri turda duzeltilecek] ("cattle",            "faostat",   "Cattle Population",              "",      "food",    1961, 3, ["world"]),
    # [FAOSTAT devre disi - API formati calismadi, ayri turda duzeltilecek] ("sheep",             "faostat",   "Sheep Population",               "",      "food",    1961, 3, ["world"]),
    # [FAOSTAT devre disi - API formati calismadi, ayri turda duzeltilecek] ("chicken",           "faostat",   "Chicken Population",             "",      "food",    1961, 3, ["world"]),
]

WORLD_ONLY = {"FP.CPI.TOTL.ZG", "GB.XPD.RSDV.GD.ZS"}

# tier 3'te havuzu genisletmek icin kapsamlari tamamla
ALL_SCOPES = ["world", "europe", "asia", "africa", "americas", "middle_east"]

SOURCE_LABEL = {"worldbank": "World Bank",
                "owid": "Our World in Data",
                "faostat": "FAO (UN)"}


def build():
    rows = []
    for (code, source, label, unit, theme, start, tier, scopes) in INDICATORS:
        use = ["world"] if code in WORLD_ONLY else scopes
        if tier == 3 and code not in WORLD_ONLY:
            use = ALL_SCOPES
        for scope in use:
            rows.append({
                "id": f"{code.replace('.', '_').lower()}__{scope}",
                "source": source,
                "indicator": code,
                "scope": scope,
                "start": start,
                "end": END_YEAR,
                "top_n": 12,
                "theme": theme,
                "tier": tier,
                "unit": unit,
                "title": f"Top 10 Countries by {label} in {SCOPE_LABEL[scope]}",
                "chart_title": f"{label} - {SCOPE_LABEL[scope].title()}",
                "source_label": SOURCE_LABEL[source],
            })

    buckets = {1: [], 2: [], 3: []}
    for r in rows:
        buckets[r["tier"]].append(r)

    out = []
    for tier in (1, 2, 3):
        groups = {}
        for r in buckets[tier]:
            groups.setdefault(r["indicator"], []).append(r)
        while groups:
            for key in list(groups):
                if groups[key]:
                    out.append(groups[key].pop(0))
                if not groups[key]:
                    del groups[key]
    return out


def main():
    topics = build()
    with open("topics.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump({"topics": topics}, f, sort_keys=False, allow_unicode=True)
    t = {1: 0, 2: 0, 3: 0}
    for x in topics:
        t[x["tier"]] += 1
    print(f"{len(topics)} konu | tier1 {t[1]} tier2 {t[2]} tier3 {t[3]}")
    for i, x in enumerate(topics[:12], 1):
        print(f"  {i:2d}. {x['title']}")


if __name__ == "__main__":
    main()
