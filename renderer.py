#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EveryYearCounts — renderer.py
Skia ile cizim + FFmpeg stdin pipe ile encode. Diske tek frame yazilmaz.

KILITLI STIL (degistirme):
  - Beyaz arka plan
  - Keskin kose (yuvarlatma yok)
  - Yillar tek tek artar
  - Skala sadece lider bara normalize; zoom/nefes efekti YOK
  - Sira degisiminde overshoot + kisa glow pulse
  - Odometer sayilar (PCHIP interpolasyondan dogal akar)
"""
import os
import subprocess
import numpy as np
import skia
from scipy.interpolate import PchipInterpolator

FPS = 60

# ------------------------------------------------------------------ tema
BG_TOP, BG_BOT = 0xFFFFFFFF, 0xFFF2F3F6
TEXT_MAIN = 0xFF1A1C22
TEXT_DIM  = 0x881A1C22
YEAR_TINT = 0x1E1A1C22
GLOW_DUR  = 0.45

PALETTE = [0xFFFF5D5D, 0xFF4DA3FF, 0xFFFFC145, 0xFF4DE0A6, 0xFFB07CFF,
           0xFFFF8A3D, 0xFF3DDCE0, 0xFFFF6FB5, 0xFFA8E34D, 0xFF7C8CFF,
           0xFFE0554D, 0xFF56C1FF, 0xFFEED055, 0xFF57D98F, 0xFFC98CFF,
           0xFFFFA9A9, 0xFF8FC7FF, 0xFF6FD1B0, 0xFFD3A6FF, 0xFFFFB870]

FONT_MGR = skia.FontMgr()
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

# Inter — grafik/veri gazeteciliginin standardi (FT, Datawrapper, OWID ayni aileyi kullanir).
# Repoya gomulu; sistem fontuna bagimli degiliz, her makinede ayni gorunur.
_WEIGHT_FILES = {
    "regular":   "Inter-Regular.ttf",
    "semibold":  "Inter-SemiBold.ttf",
    "bold":      "Inter-Bold.ttf",
    "extrabold": "Inter-ExtraBold.ttf",
}
_TYPEFACES = {}

def _typeface(weight):
    if weight not in _TYPEFACES:
        path = os.path.join(FONT_DIR, _WEIGHT_FILES[weight])
        tf = skia.Typeface.MakeFromFile(path) if os.path.exists(path) else None
        if tf is None:                                  # son care: sistem fontu
            style = (skia.FontStyle.Bold() if weight in ("bold", "extrabold")
                     else skia.FontStyle.Normal())
            tf = FONT_MGR.matchFamilyStyle("Inter", style) or \
                 FONT_MGR.matchFamilyStyle("", style)
        _TYPEFACES[weight] = tf
    return _TYPEFACES[weight]


def make_font(size, weight="bold", spacing=0.0):
    f = skia.Font(_typeface(weight), size)
    f.setEdging(skia.Font.Edging.kAntiAlias)
    f.setSubpixel(True)
    if spacing:
        f.setScaleX(1.0)
    return f


def draw_tracked(canvas, text, x, y, font, paint, tracking=0.0):
    """Harf araligi (tracking) ile yazi — marka bloklarinda kullanilir."""
    if not tracking:
        canvas.drawString(text, x, y, font, paint)
        return font.measureText(text)
    cx = x
    for ch in text:
        canvas.drawString(ch, cx, y, font, paint)
        cx += font.measureText(ch) + tracking
    return cx - x


# ------------------------------------------------------------------ layout
class Layout:
    """Tum ekran gecmesi gereken olculer tek yerde."""
    def __init__(self, kind):
        self.kind = kind
        if kind == "short":                      # dikey 9:16
            self.W, self.H = 1080, 1920
            self.n_bars   = 10
            self.mL, self.mR = 60, 300
            self.mT, self.mB = 520, 230
            self.f_label = make_font(37, "semibold")
            self.f_value = make_font(33, "bold")
            self.f_title = make_font(62, "extrabold")
            self.f_sub   = make_font(30, "regular")
            self.f_year  = make_font(200, "extrabold")
            self.f_brand = make_font(34, "extrabold")
            self.f_tag   = make_font(22, "semibold")
            self.f_src   = make_font(24, "regular")
            self.brand_y = 92
            self.title_y, self.sub_y = 205, 258
            self.rule_y  = 300
            self.gap_ratio = 0.30
        else:                                    # yatay 16:9
            self.W, self.H = 1920, 1080
            self.n_bars   = 10
            self.mL, self.mR = 90, 300
            self.mT, self.mB = 210, 110
            self.f_label = make_font(34, "semibold")
            self.f_value = make_font(31, "bold")
            self.f_title = make_font(56, "extrabold")
            self.f_sub   = make_font(27, "regular")
            self.f_year  = make_font(180, "extrabold")
            self.f_brand = make_font(30, "extrabold")
            self.f_tag   = make_font(20, "semibold")
            self.f_src   = make_font(22, "regular")
            self.brand_y = 70
            self.title_y, self.sub_y = 140, 180
            self.rule_y  = 200
            self.gap_ratio = 0.28

    @property
    def plot_w(self):
        return self.W - self.mL - self.mR

    @property
    def row_h(self):
        return (self.H - self.mT - self.mB) / self.n_bars


# ------------------------------------------------------------------ easing
def ease_overshoot(t, s=1.20):
    t = float(np.clip(t, 0.0, 1.0)) - 1.0
    return t * t * ((s + 1) * t + s) + 1.0


# ------------------------------------------------------------------ veri
class RaceData:
    """raw: {entity: [deger...]}, steps: [yil...] (yillik, tek tek artar)"""
    def __init__(self, raw, steps):
        self.entities = list(raw.keys())
        self.steps = list(steps)
        x = np.arange(len(self.steps))
        self.splines = {}
        for e, vals in raw.items():
            v = np.maximum(np.asarray(vals, dtype=float), 0.0)
            self.splines[e] = PchipInterpolator(x, v)

    def values_at(self, t):
        return {e: float(sp(t)) for e, sp in self.splines.items()}

    def label_at(self, t):
        i = int(np.clip(np.floor(t + 1e-9), 0, len(self.steps) - 1))
        return self.steps[i]


class RankTracker:
    def __init__(self, entities, trans_frames):
        self.pos  = {e: None for e in entities}
        self.src  = {e: None for e in entities}
        self.dst  = {e: None for e in entities}
        self.t0   = {e: -1 for e in entities}
        self.glow = {e: -9999 for e in entities}
        self.tf   = max(trans_frames, 1)

    def update(self, ranks, frame):
        for e, r in ranks.items():
            if self.pos[e] is None:
                self.pos[e] = self.src[e] = self.dst[e] = float(r)
                continue
            if r != self.dst[e]:
                self.src[e] = self.pos[e]
                self.dst[e] = float(r)
                self.t0[e]  = frame
                self.glow[e] = frame
        for e in ranks:
            if self.t0[e] >= 0:
                p = (frame - self.t0[e]) / self.tf
                if p >= 1.0:
                    self.pos[e] = self.dst[e]
                    self.t0[e] = -1
                else:
                    self.pos[e] = self.src[e] + (self.dst[e] - self.src[e]) * ease_overshoot(p)

    def glow_alpha(self, e, frame):
        dt = (frame - self.glow[e]) / (GLOW_DUR * FPS)
        return float(np.sin(dt * np.pi)) if 0.0 <= dt <= 1.0 else 0.0


# ------------------------------------------------------------------ format
def fmt_value(v, unit=""):
    if v >= 1e12: s = f"{v/1e12:,.2f}T"
    elif v >= 1e9: s = f"{v/1e9:,.2f}B"
    elif v >= 1e6: s = f"{v/1e6:,.1f}M"
    elif v >= 1e3: s = f"{v:,.0f}"
    elif v >= 10:  s = f"{v:,.1f}"
    else:          s = f"{v:,.2f}"
    return f"{s}{unit}"


# ------------------------------------------------------------------ cizim
def draw_brand(canvas, L):
    """Ust marka kilidi: mini bar isareti + kanal adi + tema serit."""
    p_dark = skia.Paint(AntiAlias=True, Color=TEXT_MAIN)
    # mini bar isareti (logodaki formun kucugu)
    bx, by = L.mL, L.brand_y - 26
    bh, bg = 8, 5
    for i, frac in enumerate([1.0, 0.66, 0.40]):
        canvas.drawRect(skia.Rect.MakeXYWH(bx, by + i * (bh + bg), 42 * frac, bh),
                        skia.Paint(AntiAlias=True, Color=PALETTE[i]))
    # kanal adi (harf aralikli, kucuk ama net)
    draw_tracked(canvas, "EVERYYEARCOUNTS", bx + 62, L.brand_y,
                 L.f_brand, p_dark, tracking=1.6)


def draw_header(canvas, L, meta):
    p_main = skia.Paint(AntiAlias=True, Color=TEXT_MAIN)
    p_dim  = skia.Paint(AntiAlias=True, Color=TEXT_DIM)

    draw_brand(canvas, L)
    canvas.drawString(meta["title"], L.mL, L.title_y, L.f_title, p_main)
    canvas.drawString(meta["subtitle"], L.mL, L.sub_y, L.f_sub, p_dim)

    # ince ayrac cizgi + solda renkli vurgu
    canvas.drawRect(skia.Rect.MakeXYWH(L.mL, L.rule_y, 64, 4),
                    skia.Paint(AntiAlias=True, Color=PALETTE[2]))
    canvas.drawRect(skia.Rect.MakeXYWH(L.mL + 64, L.rule_y + 1.5, L.W - L.mL * 2 - 64, 1),
                    skia.Paint(AntiAlias=True, Color=0x221A1C22))


def draw_footer(canvas, L, meta):
    p_dim = skia.Paint(AntiAlias=True, Color=TEXT_DIM)
    y = L.H - 40
    label = "SOURCE"
    lw = draw_tracked(canvas, label, L.mL, y, L.f_tag,
                      skia.Paint(AntiAlias=True, Color=0x661A1C22), tracking=1.4)
    canvas.drawString(meta.get("source", ""), L.mL + lw + 14, y, L.f_src, p_dim)

    hint = "everyyearcounts"
    hw = L.f_src.measureText(hint)
    canvas.drawString(hint, L.W - hw - L.mL, y, L.f_src,
                      skia.Paint(AntiAlias=True, Color=0x551A1C22))


def draw_frame(canvas, L, data, tracker, colors, t, frame, meta):
    canvas.drawRect(skia.Rect.MakeWH(L.W, L.H), skia.Paint(
        Shader=skia.GradientShader.MakeLinear(
            [skia.Point(0, 0), skia.Point(0, L.H)], [BG_TOP, BG_BOT])))

    vals  = data.values_at(t)
    order = sorted(vals, key=vals.get, reverse=True)
    ranks = {e: i for i, e in enumerate(order)}
    tracker.update(ranks, frame)

    vmax = max(vals[order[0]], 1e-9)       # sadece lidere normalize
    bar_h = L.row_h * (1 - L.gap_ratio)

    p_main = skia.Paint(AntiAlias=True, Color=TEXT_MAIN)
    p_dim  = skia.Paint(AntiAlias=True, Color=TEXT_DIM)

    draw_header(canvas, L, meta)

    # yil sayaci
    year = str(data.label_at(t))
    yw = L.f_year.measureText(year)
    p_year = skia.Paint(AntiAlias=True, Color=YEAR_TINT)
    if L.kind == "short":
        canvas.drawString(year, L.W - yw - L.mL, L.mT - 30, L.f_year, p_year)
    else:
        canvas.drawString(year, L.W - yw - 70, L.H - 70, L.f_year, p_year)

    # barlar
    visible = sorted(vals, key=lambda x: tracker.pos[x], reverse=True)
    for e in visible:
        row = tracker.pos[e]
        if row > L.n_bars - 0.15:
            continue
        y = L.mT + row * L.row_h + (L.row_h - bar_h) / 2
        w = max(L.plot_w * vals[e] / vmax, 3.0)
        rect = skia.Rect.MakeXYWH(L.mL, y, w, bar_h)
        base = colors[e]

        ga = tracker.glow_alpha(e, frame)
        if ga > 0:
            canvas.drawRect(rect, skia.Paint(
                AntiAlias=True, Color=base, Alphaf=0.5 * ga,
                MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 16)))

        c = skia.Color4f.FromColor(base)
        c2 = skia.Color4f(c.fR * 0.74, c.fG * 0.74, c.fB * 0.74, 1.0)
        canvas.drawRect(rect, skia.Paint(AntiAlias=True,
            Shader=skia.GradientShader.MakeLinear(
                [skia.Point(0, y), skia.Point(0, y + bar_h)], [c.toColor(), c2.toColor()])))

        ty = y + bar_h / 2 + L.f_label.getSize() * 0.36
        lw = L.f_label.measureText(e)
        val_s = fmt_value(vals[e], meta.get("unit", ""))
        vw = L.f_value.measureText(val_s)

        if lw + 40 < w:                       # etiket bar icine sigiyor
            canvas.drawString(e, L.mL + 22, ty, L.f_label,
                              skia.Paint(AntiAlias=True, Color=0xFF101218))
            vx = L.mL + w + 16
            if vx + vw > L.W - 20:            # tasacaksa bar icine sagdan hizala
                canvas.drawString(val_s, L.mL + w - vw - 22, ty, L.f_value,
                                  skia.Paint(AntiAlias=True, Color=0xFF101218))
            else:
                canvas.drawString(val_s, vx, ty, L.f_value, p_main)
        else:                                 # etiket sigmiyor, ikisi de disarida
            canvas.drawString(e, L.mL + w + 16, ty, L.f_label, p_main)
            canvas.drawString(val_s, L.mL + w + 26 + lw, ty, L.f_value, p_dim)

    draw_footer(canvas, L, meta)


# ------------------------------------------------------------------ render
def render_card(out_path, title, subtitle, index, total, seconds=2.0, crf=18):
    """
    Derleme segmentleri arasina giren gecis karti.
    Mid-roll reklamlar buraya denk gelsin diye 2 sn sabit; izleyici kopmaz.
    Uzun form ile ayni cozunurluk/codec, boylece -c copy ile birlesir.
    """
    L = Layout("long")
    f_num  = make_font(150, "extrabold")
    f_tit  = make_font(74, "extrabold")
    f_sub  = make_font(34, "regular")

    surface = skia.Surface(L.W, L.H)
    canvas = surface.getCanvas()
    canvas.drawRect(skia.Rect.MakeWH(L.W, L.H), skia.Paint(
        Shader=skia.GradientShader.MakeLinear(
            [skia.Point(0, 0), skia.Point(0, L.H)], [BG_TOP, BG_BOT])))

    accent = PALETTE[(index - 1) % len(PALETTE)]
    canvas.drawRect(skia.Rect.MakeXYWH(0, 0, L.W, 12),
                    skia.Paint(AntiAlias=True, Color=accent))
    draw_brand(canvas, L)

    num = f"{index:02d}"
    canvas.drawString(num, L.mL, L.H / 2 - 40, f_num,
                      skia.Paint(AntiAlias=True, Color=accent))
    canvas.drawString(f"of {total:02d}", L.mL + f_num.measureText(num) + 22,
                      L.H / 2 - 40, f_sub,
                      skia.Paint(AntiAlias=True, Color=TEXT_DIM))
    canvas.drawString(title, L.mL, L.H / 2 + 60, f_tit,
                      skia.Paint(AntiAlias=True, Color=TEXT_MAIN))
    canvas.drawString(subtitle, L.mL, L.H / 2 + 118, f_sub,
                      skia.Paint(AntiAlias=True, Color=TEXT_DIM))

    img = surface.makeImageSnapshot().tobytes()
    ff = subprocess.Popen([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgba",
        "-s", f"{L.W}x{L.H}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
        "-pix_fmt", "yuv420p", out_path
    ], stdin=subprocess.PIPE)
    try:
        for _ in range(int(seconds * FPS)):
            ff.stdin.write(bytes(img))
    finally:
        ff.stdin.close()
        ff.wait()
    return out_path


def render(data, out_path, meta, kind="short",
           seconds_per_step=None, hold_end=2.5, crf=18, preset="medium",
           with_audio=True):
    L = Layout(kind)
    n = len(data.steps)
    if seconds_per_step is None:
        seconds_per_step = 0.62 if kind == "short" else 0.95
    body   = int((n - 1) * seconds_per_step * FPS)
    tail   = int(hold_end * FPS)
    trans  = int((0.62 if kind == "short" else 0.72) * FPS)

    colors  = {e: PALETTE[i % len(PALETTE)] for i, e in enumerate(data.entities)}
    tracker = RankTracker(data.entities, trans)

    ff = subprocess.Popen([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgba",
        "-s", f"{L.W}x{L.H}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_path
    ], stdin=subprocess.PIPE)

    surface = skia.Surface(L.W, L.H)
    canvas  = surface.getCanvas()
    try:
        for frame in range(body + tail):
            t = min(frame / (seconds_per_step * FPS), n - 1)
            draw_frame(canvas, L, data, tracker, colors, t, frame, meta)
            ff.stdin.write(bytes(surface.makeImageSnapshot().tobytes()))
    finally:
        ff.stdin.close()
        ff.wait()

    duration = (body + tail) / FPS
    if with_audio:
        _add_ambient(out_path, duration,
                     seed=abs(hash(meta.get("title", ""))) % 9999)
    return out_path, duration


def _add_ambient(video_path, duration, seed=0):
    """Prosedurel ambient muzigi videoya ekler. Ses tamamen kod tabanli
    uretilir (audio.py), dolayisiyla Content ID riski yoktur.
    Herhangi bir hata olursa video sessiz olarak birakilir."""
    try:
        import audio
    except ImportError:
        return video_path

    base = os.path.splitext(video_path)[0]
    wav = base + "_bg.wav"
    tmp = base + "_snd.mp4"
    try:
        audio.make_ambient(wav, duration + 0.5, seed=seed)
        r = subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", video_path, "-i", wav,
            "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
            "-shortest", tmp
        ], capture_output=True)
        if r.returncode != 0 or not os.path.exists(tmp):
            print("[ses] mux basarisiz, sessiz devam")
            return video_path
        os.replace(tmp, video_path)
        print("[ses] ambient muzik eklendi")
        return video_path
    except Exception as exc:
        print(f"[ses] atlandi: {exc}")
        return video_path
    finally:
        for f in (wav, tmp):
            if os.path.exists(f):
                try:
                    os.remove(f)
                except OSError:
                    pass
