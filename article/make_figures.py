#!/usr/bin/env python3
"""
Article figures, drawn from the files in ../results/ so every plotted value is
reproducible with ../RUN_ALL.sh.  Print-first: black line art, series told
apart by line style and marker shape (never by colour alone), one axis per
chart, legend plus direct labels, recessive grid.

  column width 252 pt (3.5 in)      text width 516 pt (7.16 in)

Run from the article/ directory:   python3 make_figures.py
"""
import json, os, re, math
from reportlab.pdfgen import canvas as C
from reportlab.lib.colors import black, white, Color

R = '../results'
OUT = 'figures'
os.makedirs(OUT, exist_ok=True)
INK2 = Color(.35, .35, .35); GRID = Color(.85, .85, .85); FILL = Color(.86, .86, .86)

def canvas(name, w, h):
    c = C.Canvas(os.path.join(OUT, name), pagesize=(w, h)); c.setLineJoin(1); c.setLineCap(1); return c

def box(c, x, y, w, h, label, pt=6.6, lw=0.7, fill=None):
    if fill: c.setFillColor(fill); c.rect(x, y, w, h, stroke=0, fill=1); c.setFillColor(black)
    c.setLineWidth(lw); c.rect(x, y, w, h, stroke=1, fill=0); c.setFont('Helvetica', pt)
    ls = label.split('\n'); n = len(ls)
    for i, l in enumerate(ls):
        c.drawCentredString(x + w / 2, y + h / 2 + (n - 1 - 2 * i) * (pt + 1) / 2 - pt / 2 + 1.5, l)

def arrow(c, x1, y1, x2, y2, lw=0.7, head=3.2):
    c.setLineWidth(lw); c.line(x1, y1, x2, y2); a = math.atan2(y2 - y1, x2 - x1)
    for s in (1, -1):
        b = a + s * 2.5; c.line(x2, y2, x2 + head * math.cos(b), y2 + head * math.sin(b))

def axes(c, x0, y0, w, h, ymax, yticks, ylab, xlab, xmax=None, xticks=()):
    c.setStrokeColor(GRID); c.setLineWidth(0.4)
    for v in yticks:
        yy = y0 + v / ymax * h; c.line(x0, yy, x0 + w, yy)
    c.setStrokeColor(black); c.setLineWidth(0.7); c.line(x0, y0, x0, y0 + h); c.line(x0, y0, x0 + w, y0)
    c.setFont('Helvetica', 6.2); c.setFillColor(INK2)
    for v in yticks:
        c.drawRightString(x0 - 3, y0 + v / ymax * h - 2, ('%g' % v))
    for v in xticks:
        xx = x0 + v / xmax * w; c.drawCentredString(xx, y0 - 8, '%g' % v); c.line(xx, y0, xx, y0 - 2)
    c.setFillColor(black); c.setFont('Helvetica', 6.6)
    c.drawCentredString(x0 + w / 2, y0 - 17, xlab)
    c.saveState(); c.translate(x0 - 22, y0 + h / 2); c.rotate(90); c.drawCentredString(0, 0, ylab); c.restoreState()

# ------------------------------------------------------------------ data
p = {k: json.load(open('%s/p_%s.json' % (R, k))) for k in ('ref', 'b', 'c')}
sweep = json.load(open('%s/sweep_power.json' % R))
fin = open('%s/FINAL_RESULTS.txt' % R).read()
fold = open('%s/fold_pitfall.txt' % R).read()

# contamination cone: the first state-level report for the uninitialised arm
blk = fin[fin.index('STATE-LEVEL DIVERGENCE LOCALISATION : ARM B'):]
blk = blk[:blk.index('###')]
root = re.search(r'state element\s+:\s+(\S+)', blk).group(1)
cone = {}
for cy, word in re.findall(r'^\s+cycle (\d+)\s+(\S+)\s+\(', blk, re.M):
    cone.setdefault(int(cy), []).append(word)
ncontam = int(re.search(r'diverging state bits : (\d+)', blk).group(1))

# ============================================================ 1. method flow
c = canvas('fig_flow.pdf', 252, 300); bw, bh, cx = 168, 21, 126
ys = [276, 244, 212, 176, 140, 104, 68, 32]
box(c, cx - bw / 2, ys[0], bw, bh, 'RTL description   |   gate-level netlist')
box(c, cx - bw / 2, ys[1], bw, bh, 'state-element correspondence map')
box(c, cx - bw / 2, ys[2], bw, bh, 'one power-up state vector')
box(c, cx - 84, ys[3], 80, bh, 'apply to RTL'); box(c, cx + 4, ys[3], 80, bh, 'apply to netlist')
box(c, cx - 84, ys[4], 80, bh, 'RTL simulation'); box(c, cx + 4, ys[4], 80, bh, 'gate simulation')
box(c, cx - bw / 2, ys[5], bw, bh, 'per-cycle four-state comparison')
box(c, cx - bw / 2, ys[6], bw, bh + 4, 'equivalence certificate\n(certified cycle window)', fill=FILL)
box(c, cx - bw / 2, ys[7], bw, bh, 'power analysis engine')
for a, b in [(0, 1), (1, 2)]: arrow(c, cx, ys[a], cx, ys[b] + bh)
arrow(c, cx - 20, ys[2], cx - 44, ys[3] + bh); arrow(c, cx + 20, ys[2], cx + 44, ys[3] + bh)
arrow(c, cx - 44, ys[3], cx - 44, ys[4] + bh); arrow(c, cx + 44, ys[3], cx + 44, ys[4] + bh)
arrow(c, cx - 44, ys[4], cx - 16, ys[5] + bh); arrow(c, cx + 44, ys[4], cx + 16, ys[5] + bh)
arrow(c, cx, ys[5], cx, ys[6] + bh + 4); arrow(c, cx, ys[6], cx, ys[7] + bh)
c.save()

# ===================================================== 2. reset-edge hazard
c = canvas('fig_reset.pdf', 252, 150)
lx, rx = 44, 244; per = (rx - lx) / 8.0
def lab(y, t): c.setFont('Helvetica', 6.6); c.drawString(6, y + 3, t)
yc = 124; lab(yc, 'CLK'); c.setLineWidth(0.7)
for i in range(8):
    a = lx + i * per
    c.line(a, yc, a + per / 2, yc); c.line(a + per / 2, yc, a + per / 2, yc + 10)
    c.line(a + per / 2, yc + 10, a + per, yc + 10); c.line(a + per, yc + 10, a + per, yc)
yr = 94; lab(yr, 'RST_N')
c.line(lx, yr, lx + per * 3.5, yr); c.line(lx + per * 3.5, yr, lx + per * 3.5, yr + 10); c.line(lx + per * 3.5, yr + 10, rx, yr + 10)
ys_ = 62; lab(ys_, 'state')
c.setDash(2, 2); c.rect(lx, ys_, per * 3.25, 13); c.setDash()
c.rect(lx + per * 3.25, ys_, rx - lx - per * 3.25, 13)
c.setFont('Helvetica', 6.0)
c.drawCentredString(lx + per * 1.6, ys_ + 4, 'x (non-resettable)')
c.drawCentredString(lx + per * 5.6, ys_ + 4, 'shared power-up vector')
dx = lx + per * 3.25; c.setDash(1.5, 1.5); c.line(dx, 52, dx, 140); c.setDash()
c.setFont('Helvetica-Bold', 6.2); c.drawCentredString(dx, 143, 'deposit')
c.setFont('Helvetica', 6.0)
c.drawString(6, 34, 'Deposit between clock edges, after the reset flush;')
c.drawString(6, 26, 'release reset with no further asserting edge.')
c.drawString(6, 14, 'Hazard: RST_N going x -> 0 is an asserting negedge and')
c.drawString(6, 6, 'fires the asynchronous reset over the deposited state.')
c.save()

# ==================================================== 3. contamination cone
c = canvas('fig_cone.pdf', 252, 196)
cyc = sorted(cone)[:8]; cw = (252 - 14) / 4.0
for row in (0, 1):
    top = 182 - row * 100; c.setLineWidth(0.7); c.line(7, top - 4, 245, top - 4)
    for k in range(4):
        if row * 4 + k >= len(cyc): break
        cy = cyc[row * 4 + k]; x = 7 + k * cw
        c.setFont('Helvetica-Bold', 6.6); c.drawCentredString(x + cw / 2, top, 'cycle %d' % cy)
        for j, wd in enumerate(cone[cy]):
            isroot = (row == 0 and k == 0)
            box(c, x + 2.5, top - 19 - j * 13.5, cw - 5, 11, root if isroot else wd, pt=5.9,
                lw=1.3 if isroot else 0.55, fill=FILL if isroot else None)
        if k: arrow(c, 7 + (k - 1) * cw + cw - 2.5, top - 13.5, x + 1.5, top - 13.5, 0.5, 2.4)
c.setFont('Helvetica', 5.9)
c.drawString(7, 13, 'Shaded: root cause. First 8 cycles shown; %d storage words' % ncontam)
c.drawString(7, 6, 'are contaminated in total.')
c.save()

# ============================================ 4. per-cycle signal energy
c = canvas('fig_profile.pdf', 516, 196)
x0, y0, w, h = 50, 34, 452, 140
ser = []
for k, name, dash, mk in [('ref', 'co-initialized (reference)', None, 'o'),
                          ('c', 'independent random', (4, 2), 's'),
                          ('b', 'no initialization', (1, 2), '^')]:
    d = p[k]; clk = d['clock_uW'] * 10.0                      # fJ per 10 ns cycle
    ser.append((name, [max(v - clk, 0.0) for v in d['profile_fJ']], dash, mk, d['peak_cycle']))
N = max(len(s[1]) for s in ser); ymax = max(max(s[1]) for s in ser) * 1.08
step = 100 if ymax < 600 else 200 if ymax < 1200 else 500
yt = list(range(0, int(ymax) + 1, step))
axes(c, x0, y0, w, h, ymax, yt, 'signal switching energy per cycle (fJ)', 'simulation cycle', N, (0, 25, 50, 75, 100))
for name, v, dash, mk, pk in ser:
    c.setLineWidth(0.9 if dash is None else 0.8)
    if dash: c.setDash(*dash)
    pth = c.beginPath()
    for i, e in enumerate(v):
        xx, yy = x0 + i / N * w, y0 + e / ymax * h
        (pth.moveTo if i == 0 else pth.lineTo)(xx, yy)
    c.drawPath(pth, stroke=1, fill=0); c.setDash()
lx = x0 + w - 128; c.setFont('Helvetica', 6.6)
c.setFillColor(white); c.rect(lx - 4, y0 + h - 40, 132, 44, stroke=0, fill=1); c.setFillColor(black)
for i, (name, v, dash, mk, pk) in enumerate(ser):
    yy = y0 + h - 8 - i * 14; c.setLineWidth(0.9)
    if dash: c.setDash(*dash)
    c.line(lx, yy + 2, lx + 16, yy + 2); c.setDash()
    c.drawString(lx + 20, yy, name)
ref = ser[0]; rk = ref[4]; ry = y0 + ref[1][rk] / ymax * h; rxp = x0 + rk / N * w
c.setLineWidth(0.7); c.circle(rxp, ry, 2.0, stroke=1, fill=0)
c.setFont('Helvetica', 6.2); c.drawString(rxp + 4, ry + 4, 'reference peak, cycle %d' % rk)
c.save()

# ================================================= 5. activity by arm (bars)
c = canvas('fig_activity.pdf', 252, 130)
gx, gw = 92, 136; ref_t = p['ref']['clean_toggles']
bars = [('co-initialized', p['ref']), ('indep. random', p['c']), ('no init', p['b'])]
c.setLineWidth(0.7); c.line(gx, 30, gx, 122)
for i, (nm, d) in enumerate(bars):
    yy = 98 - i * 30; v = d['clean_toggles']; ln = max(v / ref_t * gw, 1.0)
    if i == 0: c.setFillColor(FILL); c.rect(gx, yy, ln, 16, stroke=0, fill=1); c.setFillColor(black)
    c.setLineWidth(1.1 if i == 0 else 0.7); c.rect(gx, yy, ln, 16, stroke=1, fill=0)
    c.setFont('Helvetica', 6.6); c.drawRightString(gx - 4, yy + 5, nm)
    if i == 0: c.drawRightString(gx + ln - 4, yy + 5, '{:,}'.format(v))
    else: c.drawString(gx + ln + 3, yy + 5, '{:,}  ({:+.1f}%)'.format(v, 100.0 * (v / ref_t - 1)))
c.setFont('Helvetica', 6.6); c.drawCentredString(gx + gw / 2, 18, 'clean 0<->1 transitions, common 107-cycle window')
c.save()

# ================================= 6. two-state visibility of divergent bits
arms = []
for m in re.finditer(r'COMPARISON : (.+?)\n.*?divergent bit-cycles \(four-state\)\s+:\s+(\d+).*?'
                     r'invisible to two-state \(x vs 0\)\s+:\s+(\d+)', fold, re.S):
    nm = {'no initialisation': 'no initialization', 'independent randomisation': 'independent random'}.get(m.group(1).strip(), m.group(1).strip())
    arms.append((nm, int(m.group(2)), int(m.group(3))))
c = canvas('fig_twostate.pdf', 252, 118)
gx, gw = 92, 150
c.setLineWidth(0.7); c.line(gx, 30, gx, 108)
for i, (nm, tot, inv) in enumerate(arms):
    yy = 80 - i * 32; vis = tot - inv; fi = inv / tot * gw
    c.setFillColor(FILL); c.rect(gx, yy, fi, 16, stroke=0, fill=1); c.setFillColor(black)
    c.setLineWidth(0.7); c.rect(gx, yy, gw, 16, stroke=1, fill=0); c.line(gx + fi, yy, gx + fi, yy + 16)
    c.setFont('Helvetica', 6.6); c.drawRightString(gx - 4, yy + 5, nm)
    c.setFont('Helvetica', 6.2); c.drawCentredString(gx + fi / 2, yy + 5, '%.1f%% hidden' % (100.0 * inv / tot))
    if gw - fi > 30: c.drawCentredString(gx + fi + (gw - fi) / 2, yy + 5, 'visible')
c.setFont('Helvetica', 6.4)
c.drawCentredString(gx + gw / 2, 17, 'divergent bit-cycles; shaded: x vs 0,')
c.drawCentredString(gx + gw / 2, 9, 'invisible to a two-state comparison')
c.save()

# ================================ 7-8. power-up sweep: peak cycle, signal power
rows = sweep
def scatter(name, idx, ylab, ymax, yt, fmt):
    c = canvas(name, 252, 132)
    x0, y0, w, h = 40, 32, 202, 88
    axes(c, x0, y0, w, h, ymax, yt, ylab, 'power-up vector (seed)', len(rows) + 1, (1, 5, 10, 15, 20))
    c.setLineWidth(0.7)
    for r in rows:
        xx = x0 + r[0] / (len(rows) + 1) * w; yy = y0 + r[idx] / ymax * h
        c.rect(xx - 2, yy - 2, 4, 4, stroke=1, fill=0)
    c.save()
pk = [r[7] for r in rows]
scatter('fig_sweep_peakcycle.pdf', 7, 'peak-power cycle', 80, [0, 20, 40, 60, 80], '%d')
sp = [r[4] for r in rows]; top = math.ceil(max(sp) + 1)
scatter('fig_sweep_power.pdf', 4, 'signal power (uW)', top, list(range(0, top + 1, 2 if top <= 16 else 4)), '%.1f')

print('article figures: %s' % ', '.join(sorted(os.listdir(OUT))))
print('cone root %s, %d words contaminated; two-state arms %s' % (root, ncontam, [(a, round(100.0 * i / t, 1)) for a, t, i in arms]))
print('sweep peak cycles %s' % sorted(set(pk)))
