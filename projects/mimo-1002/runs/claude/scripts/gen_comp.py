"""Generate the two HyperFrames compositions from edit/data.json.

front/  — everything in front of the speaker: split panel, circle slide, cards/windows, subtitles.
behind/ — the 'word behind the head' only (composited under the person matte).
The HTML carries no numbers of its own: DATA is injected and the script builds DOM + one paused timeline.
"""
import json, sys, os

CSS = r"""
@font-face { font-family: "%(accent)s"; src: url("%(accent_file)s") format("truetype"); font-weight: 200 900; }
@font-face { font-family: "%(text)s"; src: url("%(text_file)s") format("truetype"); font-weight: 100 900; }
html, body { margin: 0; padding: 0; background: transparent; }
#root { position: relative; width: 100%%; height: 100%%; overflow: hidden; background: transparent; }
.layer { position: absolute; inset: 0; }
.abs { position: absolute; }
.acc { font-family: "%(accent)s", sans-serif; }
.txt { font-family: "%(text)s", sans-serif; }
.blk { display: block; }
.nowrap { white-space: nowrap; }
svg { display: block; overflow: visible; }
"""

JS = r"""
const D = __DATA__;
const LAYER = "__LAYER__";
const P = D.project, C = D.colors, T = D.type, K = D.comp, L = D.layout, S = D.shape, CV = D.curves;
const W = P.width, H = P.height;
const root = document.getElementById("root");
const tl = gsap.timeline({ paused: true });
const SINE = gsap.parseEase(CV.camera);
const FONT_A = '"' + D.fonts.accent.family + '"', FONT_T = '"' + D.fonts.text.family + '"';

function el(tag, cls, parent, style, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (style) Object.assign(e.style, style);
  if (text !== undefined) e.textContent = text;
  (parent || root).appendChild(e); return e;
}
function px(v) { return v + "px"; }
function clip(t0, t1, parent) {
  const c = el("div", "clip layer", parent || root);
  c.setAttribute("data-start", String(t0)); c.setAttribute("data-duration", String(+(t1 - t0).toFixed(3)));
  return c;
}
// graphics curves: pop = 0.85 -> 1.04 -> 1 in two expo.out segments
function pop(target, t, origin) {
  if (origin) gsap.set(target, { transformOrigin: origin });
  tl.fromTo(target, { scale: CV.pop.from, opacity: 0 }, { scale: CV.pop.over, opacity: 1, duration: CV.pop.d1, ease: CV.graphics_in }, t);
  tl.to(target, { scale: 1, duration: CV.pop.d2, ease: CV.graphics_in }, t + CV.pop.d1);
}
function hideUntil(target, t) { tl.set(target, { autoAlpha: 0 }, 0); tl.set(target, { autoAlpha: 1 }, t); }
function exitOut(target, t1) {
  tl.to(target, { opacity: 0, y: -0.012 * H, duration: CV.out, ease: CV.graphics_out }, t1 - CV.out);
}
function card(parent, x, y, w, h, extra) {
  return el("div", "abs", parent, Object.assign({ left: px(x), top: px(y), width: px(w), height: px(h),
    background: C.dark2, border: S.stroke + "px solid " + C.stroke, borderRadius: px(S.radius),
    boxShadow: "0 " + px(Math.round(S.shadow_blur / 3)) + " " + px(S.shadow_blur) + " " + C.shadow, boxSizing: "border-box",
    overflow: "hidden" }, extra || {}));
}
function text(parent, s, kind, size, weight, color, style) {
  return el("div", (kind === "accent" ? "acc" : "txt") + " nowrap", parent,
    Object.assign({ fontSize: px(size), fontWeight: String(weight), color: color || C.white, lineHeight: String(K.title_h) }, style || {}), s);
}
// ---- self-drawn icons (SVG) -------------------------------------------------
const NS = "http://www.w3.org/2000/svg";
function svg(parent, w, h, style) {
  const s = document.createElementNS(NS, "svg"); s.setAttribute("width", w); s.setAttribute("height", h);
  s.setAttribute("viewBox", "0 0 100 100"); Object.assign(s.style, style || {}); parent.appendChild(s); return s;
}
function path(s, d, color, width, fill) {
  const p = document.createElementNS(NS, "path"); p.setAttribute("d", d); p.setAttribute("fill", fill || "none");
  p.setAttribute("stroke", color); p.setAttribute("stroke-width", width || 9); p.setAttribute("stroke-linecap", "round");
  p.setAttribute("stroke-linejoin", "round"); s.appendChild(p); return p;
}
const ICON = {
  check: "M18 52 L42 74 L84 26", cross: "M24 24 L76 76 M76 24 L24 76",
  quote: "M20 62 Q20 34 42 28 M20 62 a10 10 0 1 0 0.1 0 M58 62 Q58 34 80 28 M58 62 a10 10 0 1 0 0.1 0",
  target: "M50 12 a38 38 0 1 0 0.1 0 M50 30 a20 20 0 1 0 0.1 0 M50 46 a4 4 0 1 0 0.1 0",
  doc: "M26 10 L62 10 L80 28 L80 90 L26 90 Z M62 10 L62 28 L80 28 M38 46 L68 46 M38 60 L68 60 M38 74 L58 74",
  pen: "M22 80 L30 60 L70 20 L82 32 L42 72 Z M62 28 L74 40 M20 92 L82 92",
  folder_back: "M8 24 L38 24 L46 34 L92 34 L92 86 L8 86 Z",
  folder_front: "M8 44 L92 44 L86 86 L14 86 Z",
};
function drawLine(p, t, dur) {
  const len = p.getTotalLength();
  tl.set(p, { strokeDasharray: len, strokeDashoffset: len, opacity: 0 }, 0);
  tl.set(p, { opacity: 1 }, t);
  tl.to(p, { strokeDashoffset: 0, duration: dur || CV.draw, ease: CV.graphics_in }, t);
}
function verdict(parent, kind, x, y, size, color, t) {
  const s = svg(parent, size, size, { position: "absolute", left: px(x), top: px(y) });
  const p = path(s, ICON[kind], color, 11); drawLine(p, t - 1 / P.fps);  // a frame early: thin line shows late
  return s;
}
// typing: substring driven by a tweened counter, cursor blinks a finite number of times
function typeText(node, s, t, cps, cursorParent) {
  const o = { n: 0 }; node.textContent = "";
  const dur = s.length / cps;
  tl.to(o, { n: s.length, duration: dur, ease: "none", onUpdate: () => { node.textContent = s.slice(0, Math.round(o.n)); } }, t);
  tl.set(o, { n: 0, onUpdate: () => { node.textContent = ""; } }, 0);
  return dur;
}
function counter(node, from, to, t, dur) {
  const o = { v: from };
  tl.set(o, { v: from, onUpdate: () => { node.textContent = String(Math.round(o.v)); } }, 0);
  tl.to(o, { v: to, duration: dur, ease: "expo.out", onUpdate: () => { node.textContent = String(Math.round(o.v)); } }, t);
}

// =================================================================== FRONT
function buildFront() {
  // ---------- split panels (opaque, no blur), bottom edge line
  D.camera.modes.forEach((m, mi) => {
    if (m.mode !== "split") return;
    const c = clip(m.t0, m.t1);
    const panel = el("div", "abs", c, { left: "0px", top: "0px", width: px(W), height: px(L.split.h), background: C.dark,
      transformOrigin: "50% 0%" });
    const line = el("div", "abs", c, { left: "0px", top: px(L.split.h - L.split.line / 2), width: px(W), height: px(L.split.line),
      background: C.accent2 });
    if (m.open) {
      const o = { p: 0 };
      const apply = () => { const y = SINE(o.p) * L.split.h; panel.style.height = px(y); line.style.top = px(y - L.split.line / 2); };
      tl.set(o, { p: 0, onUpdate: apply }, 0);
      tl.to(o, { p: 1, duration: m.open[1] - m.open[0], ease: "none", onUpdate: apply }, m.open[0]);
    }
  });
  // ---------- circle slide: opaque fill with a real circular hole; ring around it
  D.camera.modes.forEach((m) => {
    if (m.mode !== "circle") return;
    const c = clip(m.t0, m.t1);
    const slide = el("div", "layer", c, { background: C.dark });
    const ring = el("div", "abs", c, { borderRadius: "50%", border: L.circle.ring + "px solid " + C.accent2, boxSizing: "border-box" });
    // hole radius and centre per frame come from the camera (same numbers that place the plate)
    const path = D.hole_path.filter((h) => h[0] >= m.t0 * P.fps - 1 && h[0] <= m.t1 * P.fps + 1);
    const byN = {}; path.forEach((h) => { byN[h[0]] = h; });
    const o = { t: m.t0 };
    const apply = () => {
      const n = Math.round(o.t * P.fps); const h = byN[n] || path[path.length - 1];
      const r = h[3], cx = h[1], cy = h[2];
      const mk = "radial-gradient(circle " + px(r) + " at " + px(cx) + " " + px(cy) + ", transparent " + px(r - 0.75) + ", #000 " + px(r + 0.75) + ")";
      slide.style.webkitMaskImage = mk; slide.style.maskImage = mk;
      Object.assign(ring.style, { left: px(cx - r - L.circle.ring / 2), top: px(cy - r - L.circle.ring / 2),
        width: px(2 * r + L.circle.ring), height: px(2 * r + L.circle.ring) });
    };
    tl.set(o, { t: m.t0, onUpdate: apply }, 0);
    tl.to(o, { t: m.t1, duration: m.t1 - m.t0, ease: "none", onUpdate: apply }, m.t0);
    // dark corners outside the starting circle fade in / out instead of popping
    tl.fromTo([slide, ring], { opacity: 0 }, { opacity: 1, duration: L.circle.corner_fade, ease: CV.graphics_in }, m.shrink[0]);
    tl.to([slide, ring], { opacity: 0, duration: L.circle.corner_fade, ease: CV.graphics_out }, m.expand[1] - L.circle.corner_fade);
  });
  const SCX = L.split.content, SLX = L.slide_content;
  D.graphics.forEach((g) => {
    if (g.kind === "behind_word") return;
    const c = clip(g.t0, g.t1);
    const box = el("div", "abs", c, {});
    const area = (g.kind === "slide") ? SLX : SCX;
    Object.assign(box.style, { left: px(area[0]), top: px(area[1]), width: px(area[2] - area[0]), height: px(area[3] - area[1]) });
    const BW = area[2] - area[0], BH = area[3] - area[1];
    const h = BUILD[g.kind](g, box, BW, BH);
    if (h) box.style.top = px(area[1] + Math.max(0, (BH - h) / 2));
    exitOut(box, g.t1);
  });
  buildSubtitles();
}

const BUILD = {
  hook(g, box, BW) {
    let y = 0;
    g.lines.forEach((ln, li) => {
      const size = g.sizes[li], accent = li === g.accent_line;
      const row = el("div", "abs nowrap", box, { left: "0px", top: px(y), width: px(BW), display: "flex", gap: px(size * 0.28) });
      ln.forEach((w, wi) => {
        const s = el("div", "acc", row, { fontSize: px(size), fontWeight: accent ? "600" : "800", lineHeight: "1.08",
          color: accent ? C.accent : C.white, display: "inline-block" }, accent ? w : w.toUpperCase());
        pop(s, Math.max(0, g.word_t[li][wi]), "0% 100%");
      });
      y += size * (accent ? 1.25 : 1.1);
    });
    return y;
  },
  vs(g, box, BW) {
    const cw = (BW - K.vs_badge - 2 * K.gap) / 2, ch = K.vs_card_h, y = 0;
    g.cards.forEach((cd, i) => {
      const x = i === 0 ? 0 : cw + K.vs_badge + 2 * K.gap;
      const wrap = el("div", "abs", box, { left: px(x), top: px(y), width: px(cw), height: px(ch) });
      const cc = card(wrap, 0, 0, cw, ch);
      const ic = svg(cc, K.check * 1.5, K.check * 1.5, { position: "absolute", left: px(K.pad), top: px(K.pad) });
      const ip = path(ic, ICON[cd.icon], C.accent2, 7);
      const tt = el("div", "txt", cc, { position: "absolute", left: px(K.pad), right: px(K.pad), bottom: px(K.pad),
        fontSize: px(T.body_strong), fontWeight: "600", color: C.white, lineHeight: String(K.title_h) }, cd.title);
      pop(wrap, cd.t, i === 0 ? "0% 50%" : "100% 50%");
      drawLine(ip, cd.t + 0.1);
      const v = verdict(cc, cd.verdict, cw - K.pad - K.check * 1.4, K.pad, K.check * 1.4, cd.verdict === "check" ? C.accent : C.muted, cd.vt);
      if (cd.verdict === "cross") tl.to(tt, { opacity: K.dim, duration: CV.grow, ease: CV.graphics_in }, cd.vt);
      else tl.to(cc, { borderColor: C.accent, duration: CV.grow, ease: CV.graphics_in }, cd.vt);
    });
    const b = el("div", "acc", box, { position: "absolute", left: px(BW / 2 - K.vs_badge / 2), top: px(y + ch / 2 - K.vs_badge / 2),
      width: px(K.vs_badge), height: px(K.vs_badge), borderRadius: "50%", background: C.accent, color: C.dark,
      fontSize: px(T.vs * 0.62), fontWeight: "800", display: "flex", alignItems: "center", justifyContent: "center" }, "VS");
    pop(b, g.vs_t, "50% 50%");
    return ch;
  },
  window(g, box, BW) {
    const lh = Math.round(T.body * K.line_h);
    const h0 = K.header_h + K.pad * 2 + lh;
    const win = card(box, 0, 0, BW, h0, { background: C.dark2 });
    const head = el("div", "abs", win, { left: "0px", top: "0px", width: px(BW), height: px(K.header_h), borderBottom: "1px solid " + C.stroke,
      display: "flex", alignItems: "center", gap: px(K.gap * 0.5), paddingLeft: px(K.pad), boxSizing: "border-box" });
    [C.accent, C.accent2, C.muted].forEach((col) => el("div", "", head, { width: px(K.check * 0.36), height: px(K.check * 0.36), borderRadius: "50%", background: col }));
    el("div", "txt nowrap", head, { marginLeft: px(K.gap * 0.6), fontSize: px(T.small), fontWeight: "500", color: C.muted }, g.title);
    pop(win, g.t0, "50% 0%");
    const checks = [];
    g.lines.forEach((ln, i) => {
      const y = K.header_h + K.pad + i * lh;
      const row = el("div", "abs nowrap txt", win, { left: px(K.pad), top: px(y), height: px(lh), fontSize: px(ln.size), fontWeight: "500",
        color: C.white, display: "flex", alignItems: "center" });
      const holder = el("div", "", row, { position: "relative", display: "inline-flex", alignItems: "center" });
      const a = el("span", "", holder, {});
      let cnt = null, tail = null;
      if (ln.counter) {
        cnt = el("span", "", holder, { fontVariantNumeric: "tabular-nums", display: "inline-block", overflow: "hidden",
          width: String(String(ln.counter[0]).length) + "ch", color: C.accent, fontWeight: "700" });
        tail = el("span", "", holder, {});
      }
      const cur = el("span", "", holder, { display: "inline-block", width: px(K.cursor_w), height: px(T.body * 1.05), marginLeft: px(2),
        background: C.accent, opacity: "0" });
      const strike = el("div", "abs", holder, { left: "0px", top: "52%", width: "100%", height: px(4), background: C.accent,
        transformOrigin: "0% 50%" });
      tl.set(strike, { scaleX: 0 }, 0);
      tl.to(strike, { scaleX: 1, duration: CV.draw, ease: CV.graphics_in }, g.strike_t + i * K.stagger);
      tl.to(row, { opacity: K.dim, duration: CV.grow, ease: CV.graphics_in }, g.strike_t + i * K.stagger);
      hideUntil(row, ln.t);
      if (i > 0) tl.to(win, { height: px(h0 + i * lh), duration: CV.grow, ease: CV.graphics_in }, ln.t - 0.05);
      const d = typeText(a, ln.text, ln.t, CV.type_cps);
      if (cnt) {
        tl.set(cnt, { autoAlpha: 0 }, 0); tl.set(cnt, { autoAlpha: 1 }, ln.t + d);
        counter(cnt, 0, ln.counter[0], ln.t + d, CV.count);
        const o = { v: ln.counter[0] };
        tl.to(o, { v: ln.counter[1], duration: CV.count * 0.7, ease: "expo.out", onUpdate: () => { cnt.textContent = String(Math.round(o.v)); } }, ln.count_t[1]);
        tl.to(cnt, { width: String(String(ln.counter[1]).length) + "ch", duration: CV.grow, ease: CV.graphics_in }, ln.count_t[1] + CV.count * 0.35);
        typeText(tail, ln.tail, Math.max(ln.tail_t, ln.count_t[1] + CV.count * 0.7), CV.type_cps);
      }
      // cursor follows the typed text, then blinks a finite number of times and goes away
      const endT = ln.counter ? Math.max(ln.tail_t, ln.count_t[1] + CV.count * 0.7) + ln.tail.length / CV.type_cps : ln.t + d;
      tl.set(cur, { opacity: 1 }, ln.t);
      for (let b = 0; b < K.cursor_blinks; b++) { tl.set(cur, { opacity: 0 }, endT + 0.25 + b * 0.5); tl.set(cur, { opacity: 1 }, endT + 0.5 + b * 0.5); }
      tl.set(cur, { opacity: 0 }, endT + 0.25 + K.cursor_blinks * 0.5);
      const chk = verdict(win, "check", BW - K.pad - K.check, y + (lh - K.check) / 2, K.check, C.accent, g.check_t + i * K.stagger);
      checks.push(chk);
    });
    // cursor follows text end: measured each frame from the live span width
    tl.eventCallback("onUpdate", null);
    g.lines.forEach((ln, i) => {});
    checks.forEach((c, i) => tl.to(c, { opacity: K.dim, duration: CV.grow, ease: CV.graphics_in }, g.strike_t + i * K.stagger));
    return h0 + (g.lines.length - 1) * lh;
  },
  slide(g, box, BW, BH) {
    const no = el("div", "abs", box, { left: "0px", top: "0px", width: px(BW), height: px(K.no_card_h) });
    const cc = card(no, 0, 0, BW, K.no_card_h);
    el("div", "acc", cc, { position: "absolute", left: px(K.pad), top: "0px", height: "100%", display: "flex", alignItems: "center",
      fontSize: px(T.label), fontWeight: "700", color: C.muted }, "НЕ");
    const holder = el("div", "txt nowrap", cc, { position: "absolute", left: px(K.pad + T.label * 1.9), top: "0px", height: "100%",
      display: "flex", alignItems: "center", fontSize: px(g.no.size), fontWeight: "500", color: C.white });
    const inner = el("span", "", holder, { position: "relative", display: "inline-block" }, g.no.text);
    const strike = el("div", "abs", inner, { left: "0px", top: "52%", width: "100%", height: px(4), background: C.accent, transformOrigin: "0% 50%" });
    tl.set(strike, { scaleX: 0 }, 0);
    pop(no, g.no.t, "0% 50%");
    tl.to(strike, { scaleX: 1, duration: CV.draw, ease: CV.graphics_in }, g.no.strike_t);
    tl.to(inner, { opacity: K.dim, duration: CV.grow, ease: CV.graphics_in }, g.no.strike_t);
    // stepper: nodes fill, checks draw, progress line grows; passed steps dim, current one is accent
    const top0 = K.no_card_h + K.gap * 2.2, nx = K.node / 2;
    const rail = el("div", "abs", box, { left: px(nx - 2), top: px(top0 + K.node / 2), width: px(4), height: px((g.steps.length - 1) * K.step_row),
      background: C.stroke });
    const prog = el("div", "abs", box, { left: px(nx - 2), top: px(top0 + K.node / 2), width: px(4), height: px((g.steps.length - 1) * K.step_row),
      background: C.accent, transformOrigin: "50% 0%" });
    tl.set([rail, prog], { autoAlpha: 0 }, 0); tl.set(rail, { autoAlpha: 1 }, g.steps[0].t); tl.set(prog, { autoAlpha: 1, scaleY: 0 }, g.steps[0].t);
    g.steps.forEach((sp, i) => {
      const y = top0 + i * K.step_row;
      const row = el("div", "abs", box, { left: "0px", top: px(y), width: px(BW), height: px(K.step_row) });
      const node = el("div", "abs", row, { left: "0px", top: "0px", width: px(K.node), height: px(K.node), borderRadius: "50%",
        border: "3px solid " + C.accent, boxSizing: "border-box", background: C.dark });
      const num = el("div", "acc", node, { position: "absolute", inset: "0", display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: px(K.node * 0.42), fontWeight: "700", color: C.accent }, String(i + 1));
      const ck = svg(node, K.node * 0.62, K.node * 0.62, { position: "absolute", left: px(K.node * 0.19 - 3), top: px(K.node * 0.19 - 3) });
      const ckp = path(ck, ICON.check, C.dark, 13);
      const title = el("div", "acc nowrap", row, { position: "absolute", left: px(K.node + K.gap), top: px((K.node - T.step_title * K.title_h) / 2),
        fontSize: px(sp.title_size), fontWeight: "700", color: C.white, lineHeight: String(K.title_h) }, sp.title);
      pop(row, sp.t, "0% 50%");
      if (i > 0) tl.to(prog, { scaleY: i / (g.steps.length - 1), duration: CV.grow, ease: CV.graphics_in }, sp.t);
      tl.to(title, { color: C.accent, duration: 0.01 }, sp.t);
      const nextT = i + 1 < g.steps.length ? g.steps[i + 1].t : null;
      if (nextT !== null) {            // step done: filled node + check, row dims
        tl.to(node, { background: C.accent, duration: CV.grow, ease: CV.graphics_in }, nextT);
        tl.to(num, { opacity: 0, duration: 0.12 }, nextT);
        drawLine(ckp, nextT);
        tl.to(title, { color: C.white, duration: 0.01 }, nextT);
        tl.to(row, { opacity: 0.62, duration: CV.grow, ease: CV.graphics_in }, nextT);
      } else { tl.set(ckp, { opacity: 0 }, 0); }
      let sy = (K.node + T.step_title * K.title_h) / 2 + K.gap * 0.4;
      if (sp.sub) {
        const sub = el("div", "txt nowrap", row, { position: "absolute", left: px(K.node + K.gap), top: px(sy), fontSize: px(sp.sub_size),
          fontWeight: "500", color: C.accent2 }, sp.sub);
        sy += T.body * K.line_h;
        hideUntil(sub, sp.t + 0.1); tl.fromTo(sub, { x: -0.02 * W }, { x: 0, duration: CV.in, ease: CV.graphics_in }, sp.t + 0.1);
      }
      (sp.chips || []).forEach((cp, ci) => {
        const chip = el("div", "txt nowrap", row, { position: "absolute", left: px(K.node + K.gap), top: px(sy + ci * (K.chip_h + K.gap * 0.4)),
          height: px(K.chip_h), padding: "0 " + px(K.pad * 0.7), display: "flex", alignItems: "center", borderRadius: px(K.chip_h / 2),
          background: C.accent2, color: C.dark, fontSize: px(cp.size), fontWeight: "600", boxSizing: "border-box" }, cp.text);
        pop(chip, cp.t, "0% 50%");
      });
    });
    return null;
  },
  checklist(g, box, BW) {
    const tt = text(box, g.title, "accent", g.label_size, 700, C.accent2, { position: "absolute", left: "0px", top: "0px" });
    pop(tt, g.t0, "0% 50%");
    const y0 = g.label_size * K.title_h + K.gap;
    const lst = card(box, 0, y0, BW, K.pad * 2, {});
    pop(lst, g.items[0].t, "50% 0%");
    g.items.forEach((it, i) => {
      const y = K.pad + i * K.item_row;
      if (i > 0) tl.to(lst, { height: px(K.pad * 2 + (i + 1) * K.item_row), duration: CV.grow, ease: CV.graphics_in }, it.t - 0.05);
      else tl.set(lst, { height: px(K.pad * 2 + K.item_row) }, 0);
      const row = el("div", "abs txt nowrap", lst, { left: px(K.pad), top: px(y), height: px(K.item_row), display: "flex", alignItems: "center",
        fontSize: px(it.size), fontWeight: "500", color: C.white }, it.text);
      const bx = el("div", "abs", lst, { left: px(BW - K.pad - K.check * 1.25), top: px(y + (K.item_row - K.check * 1.25) / 2), width: px(K.check * 1.25),
        height: px(K.check * 1.25), borderRadius: px(S.radius * 0.45), border: "3px solid " + C.accent, boxSizing: "border-box" });
      const ck = verdict(bx, "check", -3, -3, K.check * 1.25 - 0, C.accent, it.t + 0.15);
      hideUntil(row, it.t); tl.fromTo(row, { x: -0.02 * W }, { x: 0, duration: CV.in, ease: CV.graphics_in }, it.t);
      pop(bx, it.t, "50% 50%");
    });
    return y0 + K.pad * 2 + g.items.length * K.item_row;
  },
  quote(g, box, BW) {
    const lb = text(box, g.label, "accent", g.label_size, 700, C.accent2, { position: "absolute", left: "0px", top: "0px" });
    pop(lb, g.t0, "0% 50%");
    const y0 = g.label_size * K.title_h + K.gap * 1.5;
    const lh = T.body_strong * K.line_h;
    const bar = el("div", "abs", box, { left: "0px", top: px(y0), width: px(K.quote_bar), height: px(g.lines.length * lh), background: C.accent,
      transformOrigin: "50% 0%" });
    tl.fromTo(bar, { scaleY: 0 }, { scaleY: 1, duration: CV.in, ease: CV.graphics_in }, g.t0 + 0.1);
    g.lines.forEach((ln, i) => {
      const row = el("div", "abs txt nowrap", box, { left: px(K.quote_bar + K.pad), top: px(y0 + i * lh), height: px(lh), display: "flex",
        alignItems: "center", fontSize: px(ln.size), fontWeight: ln.accent ? "700" : "600", color: ln.accent ? C.accent : C.white });
      const sp = el("span", "", row, { position: "relative", display: "inline-block" }, ln.text);
      hideUntil(row, ln.t); tl.fromTo(row, { x: 0.03 * W }, { x: 0, duration: CV.in, ease: CV.graphics_in }, ln.t);
      if (ln.strike_t) {
        const s = el("div", "abs", sp, { left: "0px", top: "54%", width: "100%", height: px(4), background: C.accent, transformOrigin: "0% 50%" });
        tl.set(s, { scaleX: 0 }, 0);
        tl.to(s, { scaleX: 1, duration: CV.draw, ease: CV.graphics_in }, ln.strike_t);
        tl.to(sp, { opacity: K.dim, duration: CV.grow, ease: CV.graphics_in }, ln.strike_t);
      }
    });
    return y0 + g.lines.length * lh;
  },
  folder(g, box, BW) {
    const lb = text(box, g.label, "accent", g.label_size, 700, C.accent2, { position: "absolute", left: "0px", top: "0px" });
    pop(lb, g.t0, "0% 50%");
    const y0 = g.label_size * K.title_h + K.gap * 1.5;
    const fw = K.folder_w;
    const fwrap = el("div", "abs", box, { left: "0px", top: px(y0), width: px(fw), height: px(fw) });
    const fs = svg(fwrap, fw, fw, {});
    path(fs, ICON.folder_back, C.accent, 5, C.accent);
    const front = path(fs, ICON.folder_front, C.accent2, 5, C.accent2);
    front.style.transformOrigin = "50% 86%"; front.style.transformBox = "view-box";
    pop(fwrap, g.t0 + 0.08, "0% 100%");
    tl.fromTo(front, { scaleY: 1 }, { scaleY: 0.72, duration: CV.in, ease: CV.graphics_in }, g.folder_t);
    const badge = el("div", "acc", fwrap, { position: "absolute", right: px(-K.check * 0.3), top: px(fw * 0.12), width: px(K.check * 1.5),
      height: px(K.check * 1.5), borderRadius: "50%", background: C.white, color: C.dark, display: "flex", alignItems: "center",
      justifyContent: "center", fontSize: px(K.check * 0.75), fontWeight: "800", fontVariantNumeric: "tabular-nums" }, "0");
    pop(badge, g.folder_t, "50% 50%");
    const fx = fw + K.gap * 1.2, cwid = BW - fx;
    g.files.forEach((f, i) => {
      const wrap = el("div", "abs", box, { left: px(fx), top: px(y0 + i * (K.file_h + K.gap)), width: px(cwid), height: px(K.file_h) });
      const cc = card(wrap, 0, 0, cwid, K.file_h);
      const ic = svg(cc, K.file_h * 0.5, K.file_h * 0.5, { position: "absolute", left: px(K.pad * 0.8), top: px(K.file_h * 0.25) });
      path(ic, ICON[f.icon], C.accent, 7);
      el("div", "txt nowrap", cc, { position: "absolute", left: px(K.pad * 0.8 + K.file_h * 0.5 + K.gap * 0.6), top: "0px", height: "100%",
        display: "flex", alignItems: "center", fontSize: px(f.size), fontWeight: "600", color: C.white }, f.text);
      hideUntil(wrap, f.t);
      tl.fromTo(wrap, { x: 0.06 * W, scale: CV.pop.from, opacity: 0 }, { x: 0, scale: 1, opacity: 1, duration: CV.in, ease: CV.graphics_in }, f.t);
      tl.set(badge, { textContent: String(i + 1) }, f.t + CV.in * 0.6);
    });
    const done = verdict(fwrap, "check", fw * 0.3, fw * 0.48, fw * 0.4, C.dark, g.check_t);
    return y0 + Math.max(fw, g.files.length * (K.file_h + K.gap));
  },
};

function buildSubtitles() {
  const SUB = D.subtitles;
  SUB.items.forEach((s, i) => {
    const c = clip(s.t0, s.t1);
    const wrap = el("div", "abs txt", c, { left: "0px", width: px(W), top: px(L.subtitle_y - s.size * K.title_h * s.lines.length / 2),
      textAlign: "center", fontSize: px(s.size), fontWeight: "600", color: C.white, lineHeight: String(K.title_h),
      textShadow: "0 2px " + px(Math.round(s.size * 0.28)) + " rgba(0,0,0,0.55), 0 0 2px rgba(0,0,0,0.35)" });
    s.lines.forEach((ln) => el("div", "nowrap", wrap, {}, ln));
    tl.fromTo(wrap, { opacity: 0, y: 0.004 * H }, { opacity: 1, y: 0, duration: SUB.appear, ease: CV.graphics_in }, s.t0);
  });
}

// =================================================================== BEHIND
function buildBehind() {
  const g = D.graphics.find((x) => x.kind === "behind_word");
  const c = clip(g.t0, g.t1);
  const w = el("div", "acc nowrap", c, { position: "absolute", left: px(g.left), top: px(g.cap_center_y - g.size * 0.5),
    width: px(g.width), height: px(g.size), lineHeight: px(g.size), fontSize: px(g.size), fontWeight: "800", color: C.accent,
    display: "flex", alignItems: "center", justifyContent: "flex-start", transformOrigin: "50% 60%" }, g.text);
  tl.fromTo(w, { scale: g.grow_from, opacity: 0 }, { scale: 1, opacity: 1, duration: CV.in, ease: CV.graphics_in }, g.t0);
  tl.to(w, { opacity: 0, scale: 0.97, duration: CV.out, ease: CV.graphics_out }, g.t1 - CV.out);
}

document.fonts.ready.then(() => {
  if (LAYER === "front") buildFront(); else buildBehind();
  window.__timelines["__ID__"] = tl;
  if (window.__hfForceTimelineRebind) window.__hfForceTimelineRebind();
});
"""

def main(data_json, outdir):
    d = json.load(open(data_json))
    st = json.load(open(os.path.join(os.path.dirname(data_json), "camera_states.json")))
    d["hole_path"] = [[s["n"], round(s["hole_c"][0], 2), round(s["hole_c"][1], 2), round(s["hole"], 2)] for s in st if s["mode"] == "circle"]
    for layer in ("front", "behind"):
        cid = f"reel-{layer}"
        css = CSS % {"accent": d["fonts"]["accent"]["family"], "accent_file": d["fonts"]["accent"]["file"],
                     "text": d["fonts"]["text"]["family"], "text_file": d["fonts"]["text"]["file"]}
        js = JS.replace("__DATA__", json.dumps(d, ensure_ascii=False)).replace("__LAYER__", layer).replace("__ID__", cid)
        html = f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width={d['project']['width']}, height={d['project']['height']}" />
<title>reel {layer}</title>
<script src="gsap.min.js"></script>
<style>{css}</style>
</head>
<body>
<div id="root" data-composition-id="{cid}" data-start="0" data-width="{d['project']['width']}" data-height="{d['project']['height']}" data-duration="{d['duration']}"></div>
<script>{js}</script>
</body>
</html>
"""
        os.makedirs(f"{outdir}/{layer}", exist_ok=True)
        open(f"{outdir}/{layer}/index.html", "w").write(html)
    print("written", outdir)

if __name__ == "__main__":
    main(*sys.argv[1:3])
