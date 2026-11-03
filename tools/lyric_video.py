#!/usr/bin/env python3
"""이미지 1장 + 가사 → 배경은 아주 살짝 움직이고, 가사는 한 줄씩 하이라이트되며 위로 흐르는 영상.

필요: Python 3.9+, Pillow, numpy, ffmpeg (PATH에 있거나 --ffmpeg 로 경로 지정)

사용 예
  # 노래 + 타이밍(LRC) → 완성본
  python lyric_video.py --image bg.png --lyrics song.lrc --audio song.mp3 --out lyric.mp4

  # 타이밍 없이 시험 (txt 한 줄 = 가사 한 줄, 3초 간격)
  python lyric_video.py --image bg.png --lyrics lines.txt --spacing 3 --out test.mp4

  # 한 프레임만 PNG로 확인 (레이아웃 점검용)
  python lyric_video.py --image bg.png --lyrics song.lrc --still 12.5 --out frame.png

  # 일부 구간만 미리보기
  python lyric_video.py ... --start 30 --end 45 --out preview.mp4

LRC 형식:  [00:12.30]누군가 곁에 있었으면 해
           마지막에 빈 줄 태그([03:10.00])를 넣으면 거기서 하이라이트가 꺼짐.
"""
from __future__ import annotations

import argparse
import math
import os
import re
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---------------------------------------------------------------- lyrics

LRC_TAG = re.compile(r"\[(\d+):(\d+(?:[.:]\d+)?)\]")


def parse_lyrics(path: str, spacing: float, intro: float) -> list[tuple[float, str]]:
    with open(path, encoding="utf-8-sig") as f:
        raw = f.read().splitlines()
    timed: list[tuple[float, str]] = []
    plain: list[str] = []
    for line in raw:
        tags = list(LRC_TAG.finditer(line))
        if tags:
            text = LRC_TAG.sub("", line).strip()
            for m in tags:
                sec = float(m.group(2).replace(":", "."))
                timed.append((int(m.group(1)) * 60 + sec, text))
        elif line.strip() and not re.match(r"^\[[a-z]+:", line.strip(), re.I):
            plain.append(line.strip())
    if timed:
        timed.sort(key=lambda x: x[0])
        return timed
    return [(intro + i * spacing, t) for i, t in enumerate(plain)]


# ---------------------------------------------------------------- fonts

FONT_CANDIDATES = {
    "regular": [
        "C:/Windows/Fonts/malgun.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ],
    "bold": [
        "C:/Windows/Fonts/malgunbd.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    ],
}


def pick_font(user: str | None, kind: str) -> str | None:
    if user:
        return user
    for p in FONT_CANDIDATES[kind]:
        if os.path.exists(p):
            return p
    return None


# ---------------------------------------------------------------- text sprites


class Sprite:
    """premultiplied RGB (float32, 0..255) + alpha (0..1), 중심 기준 배치."""

    def __init__(self, rgb: np.ndarray, a: np.ndarray):
        self.rgb, self.a = rgb, a
        self.h, self.w = a.shape


def render_text(text, font, color, shadow_alpha, faux_bold=0) -> Image.Image:
    size = font.size
    pad = int(size * 0.7)
    l, t, r, b = font.getbbox(text, anchor="mm", stroke_width=faux_bold)
    w, h = (r - l) + pad * 2, (b - t) + pad * 2
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).text((w / 2, h / 2), text, font=font, fill=255, anchor="mm",
                              stroke_width=faux_bold, stroke_fill=255)
    shadow = Image.new("L", (w, h), 0)
    shadow.paste(mask.filter(ImageFilter.GaussianBlur(size * 0.16)), (0, int(size * 0.05)))
    ta = np.asarray(mask, np.float32) / 255
    sa = np.asarray(shadow, np.float32) / 255 * shadow_alpha
    a = ta + sa * (1 - ta)
    rgb = ta[..., None] * np.array(color, np.float32)  # 그림자는 검정 → premult 0
    out = np.dstack([rgb, a * 255]).clip(0, 255).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def pair_sprites(img_a: Image.Image, img_b: Image.Image) -> tuple[Sprite, Sprite]:
    w, h = max(img_a.width, img_b.width), max(img_a.height, img_b.height)
    res = []
    for im in (img_a, img_b):
        c = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        c.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
        arr = np.asarray(c, np.float32)
        res.append(Sprite(arr[..., :3].copy(), arr[..., 3] / 255))
    return res[0], res[1]


def make_bar(w, h, color, alpha) -> Sprite:
    pad = int(h * 0.3)
    im = Image.new("L", (w + pad * 2, h + pad * 2), 0)
    ImageDraw.Draw(im).rounded_rectangle((pad, pad, pad + w, pad + h), radius=int(h * 0.22), fill=255)
    im = im.filter(ImageFilter.GaussianBlur(max(1.0, h * 0.06)))
    a = np.asarray(im, np.float32) / 255
    # 양 끝을 살짝 흐리게
    xs = np.linspace(0, 1, a.shape[1])
    ramp = np.clip(np.minimum(xs, 1 - xs) / 0.12, 0, 1)
    ramp = ramp * ramp * (3 - 2 * ramp)
    a = a * (0.55 + 0.45 * ramp)[None, :] * alpha
    rgb = a[..., None] * np.array(color, np.float32)
    return Sprite(rgb, a)


def composite(frame: np.ndarray, sp: Sprite, cx: float, cy: float, opacity: float):
    """frame: float32 HxWx3 (in-place)."""
    if opacity <= 0.003:
        return
    H, W = frame.shape[:2]
    x0, y0 = int(round(cx - sp.w / 2)), int(round(cy - sp.h / 2))
    fx0, fy0, fx1, fy1 = max(0, x0), max(0, y0), min(W, x0 + sp.w), min(H, y0 + sp.h)
    if fx0 >= fx1 or fy0 >= fy1:
        return
    sx0, sy0 = fx0 - x0, fy0 - y0
    sx1, sy1 = sx0 + (fx1 - fx0), sy0 + (fy1 - fy0)
    a = sp.a[sy0:sy1, sx0:sx1, None] * opacity
    region = frame[fy0:fy1, fx0:fx1]
    region *= 1 - a
    region += sp.rgb[sy0:sy1, sx0:sx1] * opacity


# ---------------------------------------------------------------- background motion


class Background:
    def __init__(self, path, W, H, zoom_min, zoom_max):
        img = Image.open(path).convert("RGB")
        self.W, self.H = W, H
        self.zmax = zoom_max
        s0 = max(W / img.width, H / img.height)
        self.cw, self.ch = img.width * s0, img.height * s0  # cover 크기 (출력 px 단위)
        bw, bh = math.ceil(self.cw * zoom_max), math.ceil(self.ch * zoom_max)
        self.base = img.resize((bw, bh), Image.LANCZOS)
        self.zoom_min, self.zoom_max = zoom_min, zoom_max

    def frame(self, z, dx, dy) -> Image.Image:
        W, H = self.W, self.H
        ww, wh = W / z, H / z  # 보이는 창 크기 (cover px)
        cx = min(max(self.cw / 2 + dx, ww / 2), self.cw - ww / 2)
        cy = min(max(self.ch / 2 + dy, wh / 2), self.ch - wh / 2)
        k = self.zmax / z  # 출력 1px 당 base px
        bx0, by0 = (cx - ww / 2) * self.zmax, (cy - wh / 2) * self.zmax
        return self.base.transform((W, H), Image.AFFINE, (k, 0, bx0, 0, k, by0), Image.BICUBIC)


# ---------------------------------------------------------------- main


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def hex_rgb(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def probe_duration(ffprobe, path):
    out = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image", required=True)
    ap.add_argument("--lyrics", required=True, help=".lrc (타이밍) 또는 .txt (줄마다 가사, --spacing 간격)")
    ap.add_argument("--audio")
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", default="1920x1080")
    ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--duration", type=float, help="전체 길이(초). 기본: 오디오 길이 또는 마지막 가사+4초")
    ap.add_argument("--start", type=float, default=0.0, help="미리보기 시작 초")
    ap.add_argument("--end", type=float, help="미리보기 끝 초")
    ap.add_argument("--still", type=float, help="이 시점 한 프레임만 PNG로 저장")
    ap.add_argument("--spacing", type=float, default=3.0, help="txt 가사일 때 줄 간격(초)")
    ap.add_argument("--intro", type=float, default=2.0, help="txt 가사일 때 첫 줄 시작(초)")
    # 레이아웃 (화면 비율 기준)
    ap.add_argument("--cx", type=float, default=0.71, help="가사 열 중심 x (0~1)")
    ap.add_argument("--top", type=float, default=0.105, help="맨 윗줄 중심 y (0~1)")
    ap.add_argument("--line-gap", type=float, default=0.078, help="줄 간격 (화면 높이 비율)")
    ap.add_argument("--font-size", type=float, default=0.042, help="글자 크기 (화면 높이 비율)")
    ap.add_argument("--col-width", type=float, default=0.38, help="가사 열/하이라이트 바 너비 (화면 너비 비율)")
    ap.add_argument("--font", help="일반 줄 폰트 파일 (기본: 맑은 고딕)")
    ap.add_argument("--font-bold", help="하이라이트 줄 폰트 파일 (기본: 맑은 고딕 Bold)")
    ap.add_argument("--text-color", default="#ffffff")
    ap.add_argument("--bar-color", default="#9d86e8")
    ap.add_argument("--bar-alpha", type=float, default=0.42)
    ap.add_argument("--shadow", type=float, default=0.55, help="글자 그림자 진하기 0~1")
    # 타이밍
    ap.add_argument("--lead", type=float, default=0.25, help="가사 시작보다 이만큼 먼저 스크롤 시작(초)")
    ap.add_argument("--scroll", type=float, default=0.5, help="한 줄 스크롤 시간(초)")
    # 배경 움직임
    ap.add_argument("--zoom-min", type=float, default=1.03)
    ap.add_argument("--zoom-max", type=float, default=1.07)
    ap.add_argument("--zoom-period", type=float, default=26.0, help="줌 인/아웃 한 사이클(초)")
    ap.add_argument("--drift", type=float, default=0.007, help="좌우 흔들림 (화면 너비 비율)")
    ap.add_argument("--fade", type=float, default=1.0, help="영상 시작/끝 페이드(초)")
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--ffmpeg", default=shutil.which("ffmpeg") or "ffmpeg")
    ap.add_argument("--ffprobe")
    args = ap.parse_args()

    W, H = (int(v) for v in args.size.lower().split("x"))
    lines = parse_lyrics(args.lyrics, args.spacing, args.intro)
    if not lines:
        sys.exit("가사가 비어 있음")
    ffprobe = args.ffprobe or os.path.join(os.path.dirname(args.ffmpeg), "ffprobe" + (".exe" if args.ffmpeg.lower().endswith(".exe") else ""))
    if not os.path.dirname(args.ffmpeg):
        ffprobe = args.ffprobe or (shutil.which("ffprobe") or "ffprobe")

    if args.duration:
        total = args.duration
    elif args.audio:
        total = probe_duration(ffprobe, args.audio)
    else:
        total = lines[-1][0] + 4.0

    # ---- fonts / sprites
    fs = int(round(args.font_size * H))
    f_reg_path, f_bold_path = pick_font(args.font, "regular"), pick_font(args.font_bold, "bold")
    if not f_reg_path:
        sys.exit("한글 폰트를 못 찾음: --font 로 .ttf/.otf 경로 지정")
    faux = 0
    if not f_bold_path or (args.font and not args.font_bold):
        f_bold_path, faux = f_reg_path, max(1, fs // 28)
    col_w = args.col_width * W
    text_rgb = hex_rgb(args.text_color)

    def fit_font(path, text, size, stroke=0):
        f = ImageFont.truetype(path, size)
        while size > 10 and f.getlength(text) + stroke * 2 > col_w * 0.94:
            size -= 1
            f = ImageFont.truetype(path, size)
        return f

    sprites: list[tuple[Sprite, Sprite] | None] = []
    for _, text in lines:
        if not text:
            sprites.append(None)
            continue
        n_img = render_text(text, fit_font(f_reg_path, text, fs), text_rgb, args.shadow)
        b_img = render_text(text, fit_font(f_bold_path, text, int(fs * 1.04), faux), text_rgb, args.shadow * 1.1, faux)
        sprites.append(pair_sprites(n_img, b_img))
    has_text = np.array([s is not None for s in sprites], np.float32)
    starts = np.array([t for t, _ in lines], np.float32)
    bar = make_bar(int(col_w), int(args.line_gap * H * 0.82), hex_rgb(args.bar_color), args.bar_alpha)

    cx, top, gap = args.cx * W, args.top * H, args.line_gap * H
    # 슬롯(0=이전 줄, 1=현재 줄, 2·3=다음 줄, 4=흐려지는 줄) → 불투명도
    slot_k = [-1.6, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0, 4.8]
    slot_v = [0.0, 0.16, 0.72, 1.0, 0.88, 0.82, 0.25, 0.0]

    bg = Background(args.image, W, H, args.zoom_min, args.zoom_max)
    zmid, zamp = (args.zoom_min + args.zoom_max) / 2, (args.zoom_max - args.zoom_min) / 2
    drift = args.drift * W
    col_x0 = int(max(0, cx - col_w / 2 - fs * 2))
    col_x1 = int(min(W, cx + col_w / 2 + fs * 2))

    def render(t: float) -> np.ndarray:
        z = zmid - zamp * math.cos(2 * math.pi * t / args.zoom_period)
        dx = drift * math.sin(2 * math.pi * t / 37.0)
        dy = drift * 0.55 * math.sin(2 * math.pi * t / 29.0 + 1.3)
        frame = np.array(bg.frame(z, dx, dy))  # uint8 HxWx3

        s = -1.0 + sum(ease((t - (st - args.lead)) / args.scroll) for st in starts)
        slots = np.arange(len(lines)) - s + 1
        lyric_fade = min(1.0, max(0.0, t / 0.8))
        region = frame[:, col_x0:col_x1].astype(np.float32)
        hl = np.clip(1 - np.abs(slots - 1), 0, 1)
        bar_a = min(1.0, float((hl * has_text).sum())) * lyric_fade
        composite(region, bar, cx - col_x0, top + gap, bar_a)
        for i in np.nonzero((slots > -1.6) & (slots < 4.8))[0]:
            pair = sprites[i]
            if pair is None:
                continue
            op = float(np.interp(slots[i], slot_k, slot_v)) * lyric_fade
            w = float(hl[i])
            n, b = pair
            y = top + slots[i] * gap
            if w < 0.999:
                composite(region, n, cx - col_x0, y, op * (1 - w))
            if w > 0.001:
                composite(region, b, cx - col_x0, y, op * w)
        frame[:, col_x0:col_x1] = region.clip(0, 255).astype(np.uint8)

        if args.fade > 0:
            f = min(1.0, t / args.fade, (total - t) / args.fade)
            if f < 1:
                frame = (frame.astype(np.float32) * max(f, 0)).astype(np.uint8)
        return frame

    if args.still is not None:
        Image.fromarray(render(args.still)).save(args.out)
        print("saved", args.out)
        return

    t0, t1 = args.start, min(args.end or total, total)
    n = int(round((t1 - t0) * args.fps))
    cmd = [args.ffmpeg, "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(args.fps), "-i", "-"]
    if args.audio:
        cmd += ["-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}", "-i", args.audio, "-map", "0:v", "-map", "1:a",
                "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", str(args.crf), "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", args.out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for i in range(n):
            t = t0 + i / args.fps
            proc.stdin.write(render(t).tobytes())
            if i % int(args.fps * 5) == 0:
                print(f"\r{t:7.1f}s / {t1:.1f}s", end="", flush=True)
    finally:
        proc.stdin.close()
        proc.wait()
    print(f"\n완료: {args.out} ({n} frames)")
    if proc.returncode:
        sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
