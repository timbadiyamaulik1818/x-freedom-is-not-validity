#!/usr/bin/env python3
"""
Switching-activity extraction + power estimation from a gate-level VCD.

Counts per-net transitions, classifies them, maps each net to its driving
cell, and applies a per-cell-type energy table.  Emits total energy, average
power, a per-cycle power profile, and the peak-power cycle.

usage: power.py <vcd> <netlist.json> <label> [period_ns] [out.json]
"""
import sys, json, re, collections

VCD, NLJSON, LABEL = sys.argv[1], sys.argv[2], sys.argv[3]
PERIOD_NS = float(sys.argv[4]) if len(sys.argv) > 4 else 10.0
OUTJSON = sys.argv[5] if len(sys.argv) > 5 else None
WIN = int(sys.argv[6]) if len(sys.argv) > 6 else 0   # compare over first WIN cycles

# ---- synthetic energy model (fJ per output transition) -------------------
E_SWITCH = {'INVX1':0.5,'BUFX1':0.7,'NAND2X1':1.0,'NOR2X1':1.0,'AND2X1':1.3,
            'OR2X1':1.3,'XOR2X1':2.0,'XNOR2X1':2.0,'MUX2X1':2.2,'AOI21X1':1.4,
            'OAI21X1':1.4,'DFFX1':6.0,'DFFRX1':7.0}
E_CLK   = {'DFFX1':2.5,'DFFRX1':2.8}      # per flop per clock edge, unconditional
LEAK_PER_AREA_NW = 0.8                    # nW per unit area
AREA = {'INVX1':1,'BUFX1':2,'NAND2X1':2,'NOR2X1':2,'AND2X1':3,'OR2X1':3,
        'XOR2X1':4,'XNOR2X1':4,'MUX2X1':4,'AOI21X1':3,'OAI21X1':3,
        'DFFX1':6,'DFFRX1':8}

# ---- netlist: output net -> cell type ------------------------------------
nl = json.load(open(NLJSON))['modules']['tinycpu']
def netname_of_bits(m):
    b2n = {}
    for name, info in m['netnames'].items():
        for i, b in enumerate(info['bits']):
            if isinstance(b, int):
                b2n.setdefault(b, (name, i))
    return b2n
b2n = netname_of_bits(nl)

out_pin = {'DFFX1':'Q','DFFRX1':'Q'}
net_cell = {}
cell_count = collections.Counter()
for cname, c in nl['cells'].items():
    t = c['type']
    cell_count[t] += 1
    pin = out_pin.get(t, 'Y')
    for b in c['connections'].get(pin, []):
        if isinstance(b, int) and b in b2n:
            net_cell[b2n[b]] = t

total_area = sum(AREA.get(t,0)*n for t,n in cell_count.items())

# ---- VCD parse -----------------------------------------------------------
id2net = {}
scope = []
timescale_ps = 1.0
with open(VCD) as f:
    # header
    for line in f:
        line = line.strip()
        if line.startswith('$timescale'):
            m = re.search(r'(\d+)\s*(fs|ps|ns|us)', line)
            if m:
                mult = {'fs':0.001,'ps':1.0,'ns':1000.0,'us':1e6}[m.group(2)]
                timescale_ps = float(m.group(1))*mult
        elif line.startswith('$scope'):
            scope.append(line.split()[2])
        elif line.startswith('$upscope'):
            scope.pop()
        elif line.startswith('$var'):
            t = line.split()
            vid, nm = t[3], t[4]
            idx = t[5] if len(t) > 6 else None
            if scope[-2:-1] == ['dut'] or (len(scope) >= 2 and scope[1] == 'dut'):
                bit = 0
                if idx and idx.startswith('['):
                    mm = re.match(r'\[(\d+)\]', idx)
                    if mm: bit = int(mm.group(1))
                id2net.setdefault(vid, []).append((nm, bit))
        elif line.startswith('$enddefinitions'):
            break

    # value changes
    cur = {}
    tog01 = collections.Counter()     # clean 0<->1 transitions per vcd id
    togx  = collections.Counter()     # transitions involving x/z
    percyc01 = collections.Counter()
    t_ps = 0
    for line in f:
        line = line.rstrip()
        if not line: continue
        if line[0] == '#':
            t_ps = int(line[1:]) * timescale_ps
            continue
        if line[0] in 'bB':
            parts = line.split()
            if len(parts) < 2: continue
            val, vid = parts[0][1:], parts[1]
            # vector: compare bitwise
            old = cur.get(vid)
            cur[vid] = val
            if old is None: continue
            ow = old.rjust(len(val), old[0] if old[0] in 'xzXZ' else '0')
            nw = val.rjust(len(ow), val[0] if val[0] in 'xzXZ' else '0')
            L = max(len(ow), len(nw)); ow = ow.rjust(L,'0'); nw = nw.rjust(L,'0')
            cyc = int(t_ps // (PERIOD_NS*1000))
            for a,b in zip(ow,nw):
                if a==b: continue
                if a in '01' and b in '01':
                    tog01[vid]+=1; percyc01[cyc]+=1
                else:
                    togx[vid]+=1
        elif line[0] in '01xzXZ':
            v, vid = line[0], line[1:]
            old = cur.get(vid); cur[vid] = v
            if old is None or old == v: continue
            cyc = int(t_ps // (PERIOD_NS*1000))
            if old in '01' and v in '01':
                tog01[vid]+=1; percyc01[cyc]+=1
            else:
                togx[vid]+=1

# ---- map toggles onto cells ---------------------------------------------
sw_energy_fJ = 0.0
clean_tog = xz_tog = 0
per_cycle_fJ = collections.Counter()
cyc_scale = {}
for vid, nets in id2net.items():
    t = None
    for nm in nets:
        if nm in net_cell: t = net_cell[nm]; break
    c01, cx = tog01.get(vid,0), togx.get(vid,0)
    clean_tog += c01; xz_tog += cx
    if t:
        sw_energy_fJ += c01 * E_SWITCH.get(t, 1.0)

# per-cycle energy: scale the global per-cycle toggle profile by mean energy/toggle
mean_e = (sw_energy_fJ / clean_tog) if clean_tog else 0.0
nflop = cell_count.get('DFFX1',0) + cell_count.get('DFFRX1',0)
clk_fJ_per_cycle = (cell_count.get('DFFX1',0)*E_CLK['DFFX1']
                    + cell_count.get('DFFRX1',0)*E_CLK['DFFRX1'])

cycles = max(percyc01.keys()) + 1 if percyc01 else 1
if WIN:
    cycles = min(cycles, WIN) if cycles else WIN
    cycles = WIN
prof = []
win_tog = 0
for c in range(cycles):
    win_tog += percyc01.get(c,0)
    prof.append(percyc01.get(c,0)*mean_e + clk_fJ_per_cycle)
sig_fJ_win = win_tog * mean_e

sim_ns = cycles * PERIOD_NS
leak_nW = total_area * LEAK_PER_AREA_NW
clk_fJ = clk_fJ_per_cycle*cycles
dyn_fJ = sig_fJ_win + clk_fJ
sig_uW = (sig_fJ_win*1e-15)/(sim_ns*1e-9)*1e6
clk_uW = (clk_fJ    *1e-15)/(sim_ns*1e-9)*1e6
dyn_uW = sig_uW + clk_uW
leak_uW = leak_nW / 1000.0
tot_uW = dyn_uW + leak_uW
peak_cyc = max(range(cycles), key=lambda c: prof[c]) if cycles else 0
peak_uW = (prof[peak_cyc]*1e-15)/(PERIOD_NS*1e-9)*1e6 if cycles else 0

res = {'label':LABEL,'cycles':cycles,'clean_toggles':win_tog,'all_toggles':clean_tog,
       'signal_uW':sig_uW,'clock_uW':clk_uW,
       'xz_transitions':xz_tog,
       'xz_fraction':(xz_tog/(clean_tog+xz_tog) if clean_tog+xz_tog else 0),
       'dynamic_uW':dyn_uW,'leakage_uW':leak_uW,'total_uW':tot_uW,
       'peak_cycle':peak_cyc,'peak_uW':peak_uW,'profile_fJ':prof,
       'total_area':total_area}

print('%-30s cyc=%-4d tog=%-6d Xtr=%-6d(%4.1f%%) Psig=%7.2f Pclk=%6.2f Pleak=%5.2f Ptot=%7.2f uW  peak=%7.2f@%d'
      % (LABEL, cycles, win_tog, xz_tog, 100*res['xz_fraction'], sig_uW, clk_uW, leak_uW, tot_uW, peak_uW, peak_cyc))
if OUTJSON:
    json.dump(res, open(OUTJSON,'w'))
