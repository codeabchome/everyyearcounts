#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EveryYearCounts — main.py
Kuyruktan sirasi gelen konuyu alir, veriyi ceker, render eder, metadata uretir.
Yukleme upload.py'a devredilir. Durum state.json'da tutulur.

Kullanim:
  python3 main.py short          # gunluk Shorts (kuyruktan 1 konu)
  python3 main.py long --theme economy   # haftalik derleme
  python3 main.py short --dry    # yuklemeden sadece render
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

import yaml

import data as datalayer
from renderer import RaceData, render, render_card

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(HERE, "state.json")
OUT_DIR = os.path.join(HERE, "out")
os.makedirs(OUT_DIR, exist_ok=True)


# ---------------------------------------------------------------- durum
def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"published_short": [], "published_long": [], "failed": {}}


def save_state(state):
    """Atomik yazim — yarim kalmis state dosyasi olusmasin."""
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    os.replace(tmp, STATE_PATH)


def load_topics():
    with open(os.path.join(HERE, "topics.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)["topics"]


def next_topic(topics, state):
    """Sirasi gelen ilk yayinlanmamis konu. 3 kez patlayan konu atlanir."""
    done = set(state["published_short"])
    for t in topics:
        if t["id"] in done:
            continue
        if state["failed"].get(t["id"], 0) >= 3:
            continue
        return t
    return None


# ---------------------------------------------------------------- metadata
def build_metadata(topic, years):
    span = f"{years[0]}–{years[-1]}"
    title = f"{topic['title']} ({span})"
    if len(title) > 100:
        title = f"{topic['title']} ({span})"[:97] + "..."

    desc = (
        f"{topic['title']}, animated year by year from {years[0]} to {years[-1]}.\n\n"
        f"Data source: {topic['source_label']}\n"
        f"Indicator: {topic['indicator']}\n\n"
        "Every stat. Every year. Ranked.\n"
        "New Shorts daily — subscribe for more data races.\n\n"
        "#datavisualization #barchartrace #statistics"
    )
    tags = ["bar chart race", "data visualization", "statistics", "ranking",
            "top 10", "country comparison", "world data",
            topic["theme"], topic["source_label"].lower()]
    return {"title": title, "description": desc, "tags": tags}


# ---------------------------------------------------------------- akislar
def run_short(dry=False):
    topics, state = load_topics(), load_state()
    topic = next_topic(topics, state)
    if topic is None:
        print("kuyruk bos — yeni konu ekle veya verileri guncelle")
        return 0

    print(f"[konu] {topic['id']}  ({topic['title']})")
    try:
        raw, years = datalayer.load_topic(topic)
    except Exception as exc:
        state["failed"][topic["id"]] = state["failed"].get(topic["id"], 0) + 1
        save_state(state)
        print(f"[hata] veri alinamadi: {exc}")
        return 1

    print(f"[veri] {len(raw)} ulke x {len(years)} yil")
    race = RaceData(raw, years)
    out = os.path.join(OUT_DIR, f"{topic['id']}_short.mp4")
    meta = {
        "title": topic["chart_title"],
        "subtitle": f"{years[0]}–{years[-1]}",
        "unit": topic.get("unit", ""),
        "source": topic["source_label"],
    }
    path, dur = render(race, out, meta, kind="short")
    print(f"[render] {path}  ({dur:.1f} sn)")

    yt = build_metadata(topic, years)
    with open(out.replace(".mp4", ".json"), "w", encoding="utf-8") as f:
        json.dump(yt, f, indent=2, ensure_ascii=False)

    if dry:
        print("[dry] yukleme atlandi")
        return 0

    import upload
    video_id = upload.upload_video(path, yt, category="27")   # 27 = Education
    state["published_short"].append(topic["id"])
    state.setdefault("log", []).append({
        "id": topic["id"], "video_id": video_id, "kind": "short",
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    save_state(state)
    print(f"[upload] https://youtu.be/{video_id}")
    return 0


def run_long(theme, dry=False):
    """Shorts olarak yayinlanmis konulardan tema bazli 8 dk derleme."""
    topics, state = load_topics(), load_state()
    done = set(state["published_short"]) - set(state["published_long"])
    pool = [t for t in topics if t["id"] in done and t["theme"] == theme]
    if len(pool) < 8:
        print(f"'{theme}' havuzunda {len(pool)} konu var, 8 gerekiyor — atlandi")
        return 0

    segment = pool[:9]
    total = len(segment)
    clips = []
    last_rows = last_unit = last_title = None
    for i, t in enumerate(segment, start=1):
        raw, years = datalayer.load_topic(t)

        # gecis karti: mid-roll reklamlar buraya denk gelsin
        card = os.path.join(OUT_DIR, f"{t['id']}_card.mp4")
        render_card(card, t["chart_title"], f"{years[0]}–{years[-1]}", i, total)
        clips.append(card)

        race = RaceData(raw, years)
        out = os.path.join(OUT_DIR, f"{t['id']}_seg.mp4")
        meta = {"title": t["chart_title"], "subtitle": f"{years[0]}–{years[-1]}",
                "unit": t.get("unit", ""), "source": t["source_label"]}
        render(race, out, meta, kind="long")
        clips.append(out)
        print(f"[segment {i}/{total}] {t['id']}")

        # kapak icin son segmentin bitis tablosunu sakla
        last_rows = sorted(((n, v[-1]) for n, v in raw.items()),
                           key=lambda x: x[1], reverse=True)
        last_unit = t.get("unit", "")
        last_title = t["chart_title"]

    final = os.path.join(OUT_DIR, f"compilation_{theme}.mp4")
    concat_list = os.path.join(OUT_DIR, "concat.txt")
    with open(concat_list, "w") as f:
        for c in clips:
            f.write(f"file '{os.path.abspath(c)}'\n")
    os.system(f'ffmpeg -y -loglevel error -f concat -safe 0 -i "{concat_list}" '
              f'-c copy "{final}"')
    print(f"[derleme] {final}")

    if dry:
        return 0

    # 3 varyantli kapak (YouTube Test & Compare icin)
    thumbs = []
    if last_rows:
        import thumbnail
        thumbs = thumbnail.build_all(f"compilation_{theme}", last_title,
                                     last_rows, last_unit)
        print("[kapak] " + ", ".join(os.path.basename(p) for p in thumbs))

    import upload
    yt = {
        "title": f"{theme.title()} Data Races — Every Year Counts Compilation",
        "description": "A full-length compilation of animated data races.\n\n"
                       "Sources: World Bank, Our World in Data.",
        "tags": ["bar chart race", "data visualization", theme, "compilation"],
    }
    video_id = upload.upload_video(final, yt, category="27",
                                   thumbnail=thumbs[0] if thumbs else None)
    state["published_long"].extend([t["id"] for t in segment])
    save_state(state)
    print(f"[upload] https://youtu.be/{video_id}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["short", "long"])
    ap.add_argument("--theme", default="economy")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    return run_short(args.dry) if args.mode == "short" else run_long(args.theme, args.dry)


if __name__ == "__main__":
    sys.exit(main())
