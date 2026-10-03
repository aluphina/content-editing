"""Build edit/edl.json: phrases -> source spans cut on the waveform envelope; inner pauses shortened."""
import sys, json, os, math
FPS = 25
sys.path.insert(0, os.path.dirname(__file__))
from envelope import load, envelope, islands

PHRASES = [  # (whisper chunks, text, reason); drop: list of (a,b) source ranges to exclude
 dict(ch=[0], text="Самая частая ошибка в personal statement —"),
 dict(ch=[1], text="это писать много красивых фраз, но не доказывать свой фит."),
 dict(ch=[2], text="Фразы вроде как «этот университет престижный, он входит в топ-100, топ-10 мира»,"),
 dict(ch=[3], text="«он мне идеально подходит», «я хочу внести вклад в общество»"),
 dict(ch=[4], text="звучат, конечно, правильно."),
 dict(ch=[6], text="Но для комиссии они почти ничего не значат."),
 dict(ch=[9], text="Вместо этого нужно писать максимально конкретно."),
 dict(ch=[11], text="Не «я интересуюсь EdTech»,"),
 dict(ch=[12], text="а, к примеру: «Мой опыт в образовательном проекте показал мне проблему персонализации обучения.", drop=[(54.8, 55.3)]),
 dict(ch=[13], text="Поэтому меня интересуют модули по Learning Technologies и Design of Learning Environments»."),
 dict(ch=[14], text="Не общее «мне нравится этот профессор»,"),
 dict(ch=[15, 16, 17], text="а именно «исследования данного профессора помогают мне развить свой вопрос в том, как технологии поддерживают обучение в определённой сфере, в adult education, к примеру»."),
 dict(ch=[18, 19], text="В моём личном эссе для UCL я связывала свои проекты с конкретными модулями и академическими направлениями программы, включая профессоров, с которыми я очень-очень хотела поработать."),
 dict(ch=[21], text="Комиссия не должна видеть ваше восхищение университетом, а именно академическую совместимость с этим вузом и программой."),
 dict(ch=[30], text="Если хочешь, я могу дать тебе шаблон блока Why This University, где ты можешь, смотря на него, написать уже свой personal statement.", tail=0.32),
]
REASON = "единственная полная попытка фразы в дубле"
REASON_CTA = "последняя и полная попытка призыва; попытка 130.9–142.3 («дать свой пример эссе») — другой вариант текста, 144.5–148.0 — оборвана"
PRE, POST = 0.07, 0.07          # head/tail around speech island (s)
INNER_MAX = 0.30                # inner pause longer than this is shortened
GAP_PHRASE = 0.22               # silence kept between phrases (incl. pads)

def extend(db, hop, a, b, floor=-19.0, lim=0.25):
    i = int(a/hop)
    while i > 0 and db[i-1] > floor and a - (i-1)*hop < lim: i -= 1
    j = int(b/hop)
    while j < len(db)-1 and db[j] > floor and j*hop - b < lim: j += 1
    return i*hop, j*hop

def main(wav, tr_json, out):
    x, sr = load(wav); db, hop = envelope(x, sr)
    chunks = json.load(open(tr_json))["chunks"]
    isl = islands(db, hop)
    segs = []
    for pi, p in enumerate(PHRASES):
        lo, hi = chunks[p["ch"][0]][0], chunks[p["ch"][-1]][1]
        mine = [extend(db, hop, a, b) for a, b in isl if lo <= a < hi]
        mine = [(a, b) for a, b in mine if not any(da <= a and b <= db_ for da, db_ in p.get("drop", []))]
        # merge islands whose gap is short; otherwise cut (gap becomes POST+PRE ~ 0.14 s)
        parts = []
        for a, b in mine:
            if parts and a - parts[-1][1] <= INNER_MAX: parts[-1][1] = b
            else: parts.append([a, b])
        for k, (a, b) in enumerate(parts):
            first, last = k == 0, k == len(parts)-1
            pre = GAP_PHRASE/2 if first and pi else PRE
            post = p.get("tail", GAP_PHRASE/2) if last else POST
            fi, fo = math.floor(max(0, a-pre)*FPS), math.ceil((b+post)*FPS)   # snap to frames
            segs.append(dict(phrase=pi, src_in=round(fi/FPS, 3), src_out=round(fo/FPS, 3), f_in=fi, f_out=fo))
    t = 0.0
    for s in segs:
        s["dur"] = round(s["src_out"] - s["src_in"], 3); s["rec_in"] = round(t, 3); t += s["dur"]; s["rec_out"] = round(t, 3)
    phrases = [dict(i=i, take="take1.mp4", text=p["text"], reason=REASON_CTA if i == len(PHRASES)-1 else REASON,
                    src_in=min(s["src_in"] for s in segs if s["phrase"] == i), src_out=max(s["src_out"] for s in segs if s["phrase"] == i))
               for i, p in enumerate(PHRASES)]
    json.dump(dict(fps=25, duration=round(t, 3), segments=segs, phrases=phrases), open(out, "w"), ensure_ascii=False, indent=1)
    print(f"{len(segs)} segments, {t:.2f}s")

if __name__ == "__main__":
    main(*sys.argv[1:4])
