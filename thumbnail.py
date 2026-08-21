#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EveryYearCounts - thumbnail.py
Uzun form videolar icin 3 varyantli kapak uretir (1280x720).
YouTube Studio'nun "Test & Compare" aracina bu 3 dosya girer.

Varyantlar:
  A  "final tablo"  - videonun son yilindaki ilk 5 bar + dev baslik
  B  "buyuk soru"   - tek dev soru/ifade + arkada silik barlar
  C  "kiyas"        - birinci vs ikinci, dev sayilarla
"""
import os
import skia

from renderer import (PALETTE, TEXT_MAIN, TEXT_DIM, make_font,
                      draw_tracked, fmt_value)

W, H = 1280, 720
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


def _bg(canvas):
    canvas.drawRect(skia.Rect.MakeWH(W, H), skia.Paint(
        Shader=skia.GradientShader.MakeLinear(
            [skia.Point(0, 0), skia.Point(0, H)], [0xFFFFFFFF, 0xFFF0F1F5])))


def _brand(canvas, y=52):
    p = skia.Paint(AntiAlias=True, Color=TEXT_MAIN)
    bx, by = 48, y - 20
    for i, frac in enumerate([1.0, 0.66, 0.40]):
        canvas.drawRect(skia.Rect.MakeXYWH(bx, by + i * 11, 34 * frac, 7),
                        skia.Paint(AntiAlias=True, Color=PALETTE[i]))
    draw_tracked(canvas, "EVERYYEARCOUNTS", bx + 52, y, make_font(26, "extrabold"),
                 p, tracking=1.4)


def _wrap(text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if font.measureText(t) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def variant_a(path, title, rows, unit=""):
    """Final tablo: ilk 5 bar, gercek oranlarda."""
    surf = skia.Surface(W, H)
    cv = surf.getCanvas()
    _bg(cv)
    _brand(cv)

    f_title = make_font(62, "extrabold")
    lines = _wrap(title.upper(), f_title, W - 96)[:2]
    y = 150
    for ln in lines:
        cv.drawString(ln, 48, y, f_title, skia.Paint(AntiAlias=True, Color=TEXT_MAIN))
        y += 68

    top = rows[:5]
    vmax = max(v for _, v in top) or 1
    f_lab = make_font(30, "semibold")
    f_val = make_font(28, "bold")
    bar_h, gap = 52, 16
    by = y + 20
    for i, (name, val) in enumerate(top):
        w = max((W - 420) * val / vmax, 6)
        yy = by + i * (bar_h + gap)
        c = skia.Color4f.FromColor(PALETTE[i % len(PALETTE)])
        c2 = skia.Color4f(c.fR * .74, c.fG * .74, c.fB * .74, 1.0)
        cv.drawRect(skia.Rect.MakeXYWH(48, yy, w, bar_h), skia.Paint(
            AntiAlias=True, Shader=skia.GradientShader.MakeLinear(
                [skia.Point(0, yy), skia.Point(0, yy + bar_h)],
                [c.toColor(), c2.toColor()])))
        ty = yy + bar_h / 2 + 11
        val_s = fmt_value(val, unit)
        lw = f_lab.measureText(name)
        if lw + 30 < w:
            cv.drawString(name, 70, ty, f_lab,
                          skia.Paint(AntiAlias=True, Color=0xFF101218))
            cv.drawString(val_s, 48 + w + 14, ty, f_val,
                          skia.Paint(AntiAlias=True, Color=TEXT_MAIN))
        else:
            cv.drawString(name, 48 + w + 14, ty, f_lab,
                          skia.Paint(AntiAlias=True, Color=TEXT_MAIN))
            cv.drawString(val_s, 48 + w + 24 + lw, ty, f_val,
                          skia.Paint(AntiAlias=True, Color=TEXT_DIM))
    surf.makeImageSnapshot().save(path, skia.kPNG)
    return path


def variant_b(path, hook, sub=""):
    """Buyuk soru: tek dev ifade, arkada silik bar deseni."""
    surf = skia.Surface(W, H)
    cv = surf.getCanvas()
    _bg(cv)
    for i in range(6):
        w = (W - 200) * (1 - i * 0.14)
        cv.drawRect(skia.Rect.MakeXYWH(90, 150 + i * 92, w, 58),
                    skia.Paint(AntiAlias=True, Color=PALETTE[i % len(PALETTE)],
                               Alphaf=0.13))
    _brand(cv)

    size, lines, f = 96, None, None
    while size >= 52:
        f = make_font(size, "extrabold")
        lines = _wrap(hook.upper(), f, W - 130)
        if len(lines) <= 3:
            break
        size -= 6
    step = size * 1.08
    total = len(lines) * step
    y = (H - total) / 2 + step * 0.75
    for ln in lines:
        cv.drawString(ln, 65, y, f, skia.Paint(AntiAlias=True, Color=TEXT_MAIN))
        y += step
    if sub:
        cv.drawString(sub, 68, y + 6, make_font(34, "regular"),
                      skia.Paint(AntiAlias=True, Color=TEXT_DIM))
    surf.makeImageSnapshot().save(path, skia.kPNG)
    return path


def variant_c(path, title, rows, unit=""):
    """Kiyas: birinci vs ikinci, dev sayilarla."""
    surf = skia.Surface(W, H)
    cv = surf.getCanvas()
    _bg(cv)
    _brand(cv)

    cv.drawString(title.upper(), 48, 150, make_font(46, "extrabold"),
                  skia.Paint(AntiAlias=True, Color=TEXT_MAIN))

    pair = rows[:2]
    f_name = make_font(40, "semibold")
    f_num = make_font(104, "extrabold")
    for i, (name, val) in enumerate(pair):
        x = 60 + i * (W / 2 - 30)
        col = PALETTE[i]
        cv.drawRect(skia.Rect.MakeXYWH(x, 215, 100, 10),
                    skia.Paint(AntiAlias=True, Color=col))
        cv.drawString(name, x, 285, f_name,
                      skia.Paint(AntiAlias=True, Color=TEXT_MAIN))
        cv.drawString(fmt_value(val, unit), x, 400, f_num,
                      skia.Paint(AntiAlias=True, Color=col))

    cv.drawString("VS", W / 2 - 34, 340, make_font(58, "extrabold"),
                  skia.Paint(AntiAlias=True, Color=0x551A1C22))
    cv.drawRect(skia.Rect.MakeXYWH(48, 470, W - 96, 2),
                skia.Paint(AntiAlias=True, Color=0x221A1C22))
    cv.drawString("Watch the full ranking change year by year", 48, 530,
                  make_font(32, "regular"), skia.Paint(AntiAlias=True, Color=TEXT_DIM))
    surf.makeImageSnapshot().save(path, skia.kPNG)
    return path


def build_all(slug, title, rows, unit="", hook=None):
    """rows: [(ulke, son_yil_degeri), ...] sirali. 3 dosya yolu doner."""
    os.makedirs(OUT_DIR, exist_ok=True)
    hook = hook or f"WHO LEADS THE WORLD IN {title.upper()}?"
    return [
        variant_a(os.path.join(OUT_DIR, f"{slug}_thumb_a.png"), title, rows, unit),
        variant_b(os.path.join(OUT_DIR, f"{slug}_thumb_b.png"), hook,
                  "Ranked from 1960 to today"),
        variant_c(os.path.join(OUT_DIR, f"{slug}_thumb_c.png"), title, rows, unit),
    ]


if __name__ == "__main__":
    demo = [("China", 12289.0), ("United States", 4682.0), ("India", 3062.0),
            ("Russia", 1766.0), ("Japan", 944.0)]
    for p in build_all("demo", "CO2 Emissions by Country", demo, " Mt"):
        print("yazildi:", p)
