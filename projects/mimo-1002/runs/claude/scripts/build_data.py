"""Build edit/data.json (the control desk): every visible number lives here.

Timings reference transcript words (edit/words.json) by index; times are seconds of the cut.
Type sizes are fractions of u = min(W, H) (vertical frame: the 16:9-equivalent height).
"""
import json, os, sys, math
sys.path.insert(0, os.path.dirname(__file__))
import textfit as tf

E = "edit"
data = json.load(open(f"{E}/data.json"))
words = json.load(open(f"{E}/words.json"))["words"]
edl = json.load(open(f"{E}/edl.json"))
track = json.load(open(f"{E}/track.json"))
P = data["project"]; W, H, FPS = P["width"], P["height"], P["fps"]
U = min(W, H)
LEAD = P["lead"]

def wt(i, expect=None):
    w = words[i]
    if expect: assert expect.lower() in w["w"].lower(), (i, w["w"], expect)
    return round(w["t0"] - LEAD, 3)

def att(i): return round(words[i]["t0"], 3)

# ---------------------------------------------------------------- look
data["colors"] = {"white": "#FFFFFF", "accent": "#F2A33A", "accent2": "#E9D9C0", "dark": "#1B1A19",
                  "dark2": "#262321", "stroke": "#3A3531", "muted": "#9C948B", "shadow": "rgba(0,0,0,0.45)"}
data["fonts"] = {"accent": {"family": "Unbounded", "file": "fonts/Unbounded-VF.ttf"},
                 "text": {"family": "Onest", "file": "fonts/Onest-VF.ttf"}}
data["type"] = {  # px, from fractions of u
    "hook": round(0.088 * U), "label": round(0.052 * U), "behind_word": round(0.36 * U),
    "body": round(0.043 * U), "body_strong": round(0.049 * U), "small": round(0.039 * U),
    "subtitle": round(0.039 * U), "step_title": round(0.054 * U), "vs": round(0.06 * U)}
data["shape"] = {"radius": round(0.02 * U), "stroke": 2, "shadow_blur": round(0.018 * U),
                 "margin_x": round(0.06 * W), "margin_top": round(0.075 * H), "icon": round(0.06 * U)}
data["curves"] = {"graphics_in": "expo.out", "graphics_out": "expo.in", "camera": "sine.inOut",
                  "pop": {"from": 0.85, "over": 1.04, "d1": 0.22, "d2": 0.16}, "in": 0.45, "out": 0.3,
                  "grow": 0.32, "draw": 0.32, "type_cps": 30, "count": 0.9}

# ---------------------------------------------------------------- layout
split_h = round(0.44 * H)
circle = {"cx": W // 2, "cy": round(0.62 * H), "r": round(0.11 * H), "ring": 3}
circle["R0"] = W / 2          # starts inscribed in the frame width: plate and hole shrink together
circle["corner_fade"] = 0.25
data["layout"] = {
    "split": {"h": split_h, "line": 4, "content": [data["shape"]["margin_x"], data["shape"]["margin_top"],
                                                 W - data["shape"]["margin_x"], split_h - round(0.03 * H)],
              "speaker_eye_in_region": 0.36},
    "circle": circle,
    "slide_content": [data["shape"]["margin_x"], data["shape"]["margin_top"], W - data["shape"]["margin_x"],
                      circle["cy"] - circle["r"] - round(0.03 * H)],
    "subtitle_y": round(0.833 * H), "subtitle_max_w": round(0.80 * W)}

# ---------------------------------------------------------------- camera & modes (seconds of cut)
segs = edl["segments"]
seg_t = [(round(sum(s["f_out"] - s["f_in"] for s in segs[:i]) / FPS, 3),
          round(sum(s["f_out"] - s["f_in"] for s in segs[:i + 1]) / FPS, 3)) for i in range(len(segs))]
import statistics as st
def seg_face(i):
    f0 = round(seg_t[i][0] * FPS); f1 = round(seg_t[i][1] * FPS)
    tr = [t for t in track[f0:f1] if t]
    return {"cx": round(st.median(t["cx"] for t in tr), 4), "eye": round(st.median(t["eye_y"] for t in tr), 4),
            "top": round(st.median(t["top"] for t in tr), 4)}
CAM = data.setdefault("camera", {})
CAM["segments"] = [{"i": i, "t0": a, "t1": b, **seg_face(i)} for i, (a, b) in enumerate(seg_t)]
CAM["eye_third"] = 1 / 3
CAM["max_zoom"] = 1.5
# full-frame zoom per segment (only used in "full" mode); push = exponential sine.inOut zoom inside one segment
CAM["full_zoom"] = {"8": 1.10, "17": 1.0, "18": 1.0, "19": 1.0}
CAM["push"] = [{"seg": 8, "t0": 22.30, "t1": 24.20, "z0": 1.10, "z1": 1.45}]
SPLIT_OPEN = 1.2; CIRCLE_T = 1.3
modes = [
    {"mode": "split", "t0": 0.0, "t1": seg_t[7][1], "open": None, "close": "cut"},
    {"mode": "full", "t0": seg_t[8][0], "t1": seg_t[8][1]},
    {"mode": "circle", "t0": seg_t[9][0], "t1": 50.05, "shrink": [seg_t[9][0], seg_t[9][0] + CIRCLE_T],
     "expand": [50.05 - CIRCLE_T, 50.05]},
    {"mode": "full", "t0": 50.05, "t1": 52.75},
    {"mode": "split", "t0": 52.75, "t1": seg_t[-1][1], "open": [52.75, 52.75 + SPLIT_OPEN], "close": None},
]
CAM["modes"] = modes
CAM["circle_head_frac"] = 0.72      # head height / circle diameter
CAM["head_h_src"] = 0.315           # head height (hijab top to chin) as fraction of source height

# ---------------------------------------------------------------- subtitles
REPL = {"ходит": "входит", "моем": "моём", "определенной": "определённой", "AdTech": "EdTech", "Adult": "Adult",
        "education": "Education"}
SERVICE = {"в", "и", "на", "не", "мы", "с", "к", "а", "я", "по", "of", "для", "но", "он", "где", "ты", "мне", "свой", "это"}
data["subtitle_repl"] = REPL

import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from envelope import load, envelope
x, sr = load(f"{E}/audio/voice_cut.wav"); db, hop = envelope(x, sr)
noise = float(np.percentile(db, 10))
def pause_between(a, b, min_len=0.35):
    i0, i1 = int(a / hop), int(b / hop)
    low = db[i0:i1] < noise + 12; run = best = 0
    for v in low:
        run = run + 1 if v else 0; best = max(best, run)
    return best * hop >= min_len

def clean(w):
    t = w.replace("«", "").replace("»", "").replace("—", "").strip()
    core = t.rstrip(".,;:!?")
    core = REPL.get(core, core)
    keep = "?" if t.endswith("?") else ""
    return core + keep, t[-1:] in ".,;:!?" or w.rstrip().endswith(("—", "»")) and False

toks = []
for i, w in enumerate(words):
    txt, punct = clean(w["w"])
    if not txt: continue
    toks.append({"i": i, "w": txt, "t0": w["t0"], "t1": w["t1"], "punct": w["w"].rstrip()[-1:] in ".,;:!?—»"})
phrases, cur = [], []
for k, t in enumerate(toks):
    if cur:
        last = cur[-1]; text = " ".join(c["w"] for c in cur)
        brk = last["punct"] or pause_between(last["t0"], t["t0"]) or len(cur) >= 2 or len(text + " " + t["w"]) > 14
        if last["w"].lower() in SERVICE and not last["punct"] and not pause_between(last["t0"], t["t0"]):
            brk = False                                   # service word sticks to the next word
        elif t["w"].lower() in SERVICE and not t["punct"] and k + 1 < len(toks):
            brk = True                                    # service word starts the next phrase
        if brk: phrases.append(cur); cur = []
    cur.append(t)
if cur: phrases.append(cur)
subs = []
for k, ph in enumerate(phrases):
    t0 = ph[0]["t0"] - LEAD
    subs.append({"text": " ".join(c["w"] for c in ph), "t0": round(t0, 3), "words": [c["i"] for c in ph]})
END = seg_t[-1][1]
for k, s in enumerate(subs):
    nxt = subs[k + 1]["t0"] if k + 1 < len(subs) else END
    last = words[s["words"][-1]]
    gap_end = last["t1"] + 0.25
    s["t1"] = round(min(nxt, max(gap_end, s["t0"] + 0.3)) if nxt - gap_end > 0.6 else nxt, 3)
    s["t1"] = min(s["t1"], END)
# minimum on-screen time: merge too-short phrases into the next one when it stays <=2 words
def min_dur(s):
    n = len(s["text"].split()); base = 0.24 if n == 1 else 0.32
    if any(c.isdigit() for c in s["text"]) or any(c.isupper() for c in s["text"][1:]): base = max(base, 0.30)
    return base
k = 0
while k < len(subs) - 1:
    s = subs[k]
    if s["t1"] - s["t0"] < min_dur(s):
        n = subs[k + 1]; merged = s["text"] + " " + n["text"]
        if len(merged.split()) <= 3 and len(merged) <= 22 and not words[s["words"][-1]]["w"].rstrip().endswith((".", "?", "!")):
            s["text"] = merged; s["words"] += n["words"]; s["t1"] = n["t1"]; subs.pop(k + 1); continue
        deficit = min_dur(s) - (s["t1"] - s["t0"])
        if deficit <= 0.16:                       # next phrase waits a few frames
            s["t1"] = round(s["t1"] + deficit, 3); n["t0"] = s["t1"]
    k += 1
for s in subs:
    s["size"], fits = tf.fit_one_line(s["text"], "text", data["type"]["subtitle"], 600, data["layout"]["subtitle_max_w"], 0.86)
    s["lines"] = [s["text"]] if fits else (tf.balanced_break(s["text"], "text", data["type"]["subtitle"], 600,
                                                            data["layout"]["subtitle_max_w"]) or [s["text"]])
data["subtitles"] = {"appear": 0.16, "items": subs}

# ---------------------------------------------------------------- graphics timeline
G = []
c = data["curves"]
def el(kind, t0, t1, **kw):
    G.append({"kind": kind, "t0": round(t0, 3), "t1": round(t1, 3), **kw})

hook_t = [wt(0, "Самая"), wt(1, "частая"), wt(2, "ошибка"), wt(3, "в"), wt(4, "personal"), wt(5, "statement")]
el("hook", 0.0, 4.25, lines=[["САМАЯ", "ЧАСТАЯ"], ["ОШИБКА"], ["в", "personal", "statement"]],
   word_t=[hook_t[:2], hook_t[2:3], hook_t[3:]], accent_line=2, sfx=None)
el("vs", 4.42, 9.75, cards=[{"title": "Красивые фразы", "icon": "quote", "t": wt(9, "красивых"), "verdict": "cross", "vt": wt(11, "но")},
                            {"title": "Доказанный фит", "icon": "target", "t": wt(13, "доказывать"), "verdict": "check", "vt": wt(15, "фит")}],
   vs_t=wt(13, "доказывать") + 0.12)
el("window", 9.90, 21.80, title="personal_statement.docx",
   lines=[{"text": "Этот университет престижный", "t": max(9.98, wt(21, "престижный") - 0.4)},
          {"text": "Входит в ТОП-", "counter": [100, 10], "tail": "\u00a0мира", "t": wt(22, "он"), "count_t": [wt(25, "топ-100"), wt(26, "топ-10")], "tail_t": wt(27, "мира")},
          {"text": "Он мне идеально подходит", "t": wt(29, "мне")},
          {"text": "Хочу внести вклад в общество", "t": wt(33, "хочу")}],
   check_t=wt(40, "правильно"), strike_t=wt(45, "почти"))
el("slide", seg_t[9][0] + CIRCLE_T + 0.02, 36.60, no={"text": "Я интересуюсь EdTech", "t": max(seg_t[9][0] + CIRCLE_T + 0.05, wt(58, "EdTech") - 0.2), "strike_t": wt(59, "а") + 0.0},
   steps=[{"title": "Опыт", "sub": "образовательный проект", "t": wt(63, "опыт")},
          {"title": "Проблема", "sub": "персонализация обучения", "t": wt(69, "проблему")},
          {"title": "Модули", "chips": [{"text": "Learning Technologies", "t": wt(77, "Learning")},
                                        {"text": "Design of Learning Environments", "t": wt(80, "Design")}], "t": wt(75, "модули")}])
el("slide", 36.62, 48.75, no={"text": "Мне нравится этот профессор", "t": wt(84, "Не"), "strike_t": wt(89, "профессор") + 0.1},
   steps=[{"title": "Исследования", "sub": "работы профессора", "t": wt(92, "исследования")},
          {"title": "Мой вопрос", "sub": "помогают его развить", "t": wt(99, "вопрос")},
          {"title": "Технологии", "sub": "поддерживают обучение", "chips": [{"text": "Adult Education", "t": wt(110, "Adult")}], "t": wt(103, "технологии")}])
el("behind_word", wt(119, "UCL"), 52.45, text="UCL", seg=[17, 18, 19])
el("checklist", 54.05, 60.20, title="МОЁ ЭССЕ ДЛЯ UCL",
   items=[{"text": "Проекты → конкретные модули", "t": wt(126, "модулями")},
          {"text": "Академические направления", "t": wt(129, "направлениями")},
          {"text": "Профессоров, с кем хочу работать", "t": wt(132, "профессоров")}])
el("quote", 60.55, 68.10, label="ЧТО ВИДИТ КОМИССИЯ",
   lines=[{"text": "Не восхищение университетом", "t": wt(144, "восхищение"), "strike_t": wt(146, "а")},
          {"text": "а академическую совместимость", "t": wt(148, "академическую"), "accent": True},
          {"text": "с вузом и программой", "t": wt(152, "вузом")}])
el("folder", 68.35, END, label="ШАБЛОН", folder_t=wt(161, "шаблон"),
   files=[{"text": "Why This University", "icon": "doc", "t": wt(163, "Why")},
          {"text": "Мой personal statement", "icon": "pen", "t": wt(172, "написать")}],
   check_t=wt(176, "statement"))
data["graphics"] = G

# ---------------------------------------------------------------- component metrics (px), text fitted with real fonts
T = data["type"]; SC = data["layout"]["split"]["content"]; CW = SC[2] - SC[0]
comp = {"pad": round(0.03 * U), "gap": round(0.022 * U), "line_h": 1.42, "title_h": 1.12,
        "header_h": round(0.068 * U), "check": round(0.042 * U), "cursor_w": 4, "cursor_blinks": 3,
        "vs_card_h": round(0.32 * U), "vs_badge": round(0.12 * U), "node": round(0.062 * U),
        "step_row": round(0.17 * U), "no_card_h": round(0.105 * U), "item_row": round(0.088 * U),
        "folder_w": round(0.26 * U), "file_h": round(0.135 * U), "quote_bar": 6, "chip_h": round(0.062 * U),
        "content_w": CW, "dim": 0.5, "stagger": 0.08}
# hook lines: one line each, accent font shrinks to fit (not below 0.05u)
hook = next(g for g in G if g["kind"] == "hook")
hook["sizes"] = []
for li, line in enumerate(hook["lines"]):
    txt = " ".join(line); base = T["hook"] if li != hook["accent_line"] else round(T["hook"] * 0.62)
    size, ok = tf.fit_one_line(txt, "accent", base, 800 if li != hook["accent_line"] else 600, CW, 0.05 * U / base)
    assert ok, txt; hook["sizes"].append(round(size, 1))
# behind word: biggest size that keeps >=4.5 % side margins; letter 'C' centred on the head
bw = next(g for g in G if g["kind"] == "behind_word")
faces = [CAM["segments"][i] for i in bw["seg"]]
head_cx = st.median(f["cx"] for f in faces) * W
head_top = st.median(f["top"] for f in faces) * H
size = T["behind_word"]; margin = 0.045 * W
while tf.width(bw["text"], "accent", size, 800) > W - 2 * margin: size -= 1
f = tf.font("accent", size, 800)
wU = tf.width(bw["text"][0], "accent", size, 800); wC = tf.width(bw["text"][:2], "accent", size, 800) - wU
total = tf.width(bw["text"], "accent", size, 800)
left = head_cx - (wU + wC / 2)
left = min(max(left, margin), W - margin - total)
asc, desc = f.getmetrics()
bw.update(size=size, left=round(left, 1), width=round(total, 1),
          cap_center_y=round(head_top + 0.40 * CAM["head_h_src"] * H, 1), grow_from=0.84)
# fit every text box: one line, accent font down to 0.05u, text font at most -14 %; otherwise flag
def fit(item, key_text, kind, base, weight, max_w, field="size"):
    mn = (0.05 * U / base) if kind == "accent" else 0.86
    size, ok = tf.fit_one_line(item[key_text], kind, base, weight, max_w, mn)
    miss = tf.missing_glyphs(item[key_text], kind)
    assert not miss, (item[key_text], miss)
    assert ok, ("does not fit", item[key_text], round(tf.width(item[key_text], kind, base, weight)), max_w)
    item[field] = round(size, 1)
for g in G:
    k = g["kind"]
    if k == "window":
        mw = CW - 2 * comp["pad"] - comp["check"] - comp["gap"]
        for ln in g["lines"]:
            full = dict(t=ln["text"] + (str(ln["counter"][0]) + ln["tail"] if "counter" in ln else ""))
            fit(full, "t", "text", T["body"], 500, mw); ln["size"] = full["size"]
        g["title_size"] = T["small"]
    if k == "vs":
        cw = (CW - comp["vs_badge"] - 2 * comp["gap"]) / 2 - 2 * comp["pad"]
        for cd in g["cards"]:
            for wd in cd["title"].split(): assert tf.width(wd, "text", T["body_strong"], 600) <= cw, wd
    if k in ("checklist", "quote", "folder"):
        lab = dict(t=g.get("title") or g.get("label")); fit(lab, "t", "accent", T["label"], 700, CW); g["label_size"] = lab["size"]
    if k == "checklist":
        for it in g["items"]: fit(it, "text", "text", T["body"], 500, CW - 2 * comp["pad"] - comp["check"] * 1.25 - comp["gap"])
    if k == "quote":
        for ln in g["lines"]: fit(ln, "text", "text", T["body_strong"], 700 if ln.get("accent") else 600, CW - comp["quote_bar"] - comp["pad"])
    if k == "folder":
        cwid = CW - comp["folder_w"] - comp["gap"] * 1.2
        for f_ in g["files"]: fit(f_, "text", "text", T["body"], 600, cwid - comp["pad"] * 1.6 - comp["file_h"] * 0.5 - comp["gap"] * 0.6)
    if k == "slide":
        SLW = data["layout"]["slide_content"][2] - data["layout"]["slide_content"][0]
        fit(g["no"], "text", "text", T["body"], 500, SLW - 2 * comp["pad"] - T["label"] * 1.9)
        for sp in g["steps"]:
            t_ = dict(t=sp["title"]); fit(t_, "t", "accent", T["step_title"], 700, SLW - comp["node"] - comp["gap"]); sp["title_size"] = t_["size"]
            if sp.get("sub"):
                s_ = dict(t=sp["sub"]); fit(s_, "t", "text", T["body"], 500, SLW - comp["node"] - comp["gap"]); sp["sub_size"] = s_["size"]
            for cp in sp.get("chips", []): fit(cp, "text", "text", T["small"], 600, SLW - comp["node"] - comp["gap"] - comp["pad"] * 1.4)
data["comp"] = comp

# ---------------------------------------------------------------- sound design (synth whooshes, user approved)
SFX = []
def wh(peak, length, gain, kind="whoosh", up=True):
    SFX.append({"peak": round(peak, 3), "len": length, "gain": gain, "kind": kind, "rise": up})
wh(4.42 + 0.30, 0.55, 0.22)                         # VS card A lands
wh(9.90 + 0.30, 0.6, 0.24)                          # window lands
wh(22.30 + (24.20 - 22.30) / 2, 0.9, 0.22)          # push-in, peak mid-move
wh(seg_t[9][0] + CIRCLE_T / 2, 0.9, 0.30)           # circle shrink
wh(36.62 + 0.30, 0.5, 0.18)                         # slide 2 swap
wh(50.05 - CIRCLE_T / 2, 0.9, 0.30)                 # circle expand
wh(wt(119) + 0.30, 0.55, 0.32, up=False)            # UCL lands (whoosh into the hit)
wh(52.75 + SPLIT_OPEN / 2, 0.9, 0.28)               # split opens
wh(60.55 + 0.30, 0.5, 0.18)                         # quote card
wh(wt(163) + 0.30, 0.5, 0.22)                       # file 1 flies in
wh(wt(172) + 0.30, 0.5, 0.22)                       # file 2 flies in
data["sfx"] = SFX
data["mix"] = {"voice": 1.0, "target_lufs": -14.0, "true_peak": -1.0}
data["duration"] = END
json.dump(data, open(f"{E}/data.json", "w"), ensure_ascii=False, indent=1)
print("graphics", len(G), "subs", len(subs), "sfx", len(SFX), "duration", END)
for s in subs[:20]: print(f'{s["t0"]:6.2f}-{s["t1"]:6.2f} {s["text"]}')
