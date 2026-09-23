#!/usr/bin/env python3
"""Generalised state-map builder.
usage: build_map2.py <rtl.v> <preopt.json> <pre_top> <netlist.json> <nl_top> <netlist.v> <out.json>"""
import json, re, collections, hashlib, sys
RTLV, PREJ, PRETOP, NLJ, NLTOP, NLV, OUT = sys.argv[1:8]

def alias_pairs(path, top):
    m = json.load(open(path))['modules'][top]
    b2n = collections.defaultdict(list)
    for name, info in m['netnames'].items():
        if name.startswith('$'): continue
        for i, b in enumerate(info['bits']):
            if isinstance(b, int): b2n[b].append((name, i))
    pairs = []
    for b, names in b2n.items():
        for x in range(len(names)):
            for y in range(x+1, len(names)): pairs.append((names[x], names[y]))
    return pairs, m, b2n

pre_pairs, pre_m, pre_b2n = alias_pairs(PREJ, PRETOP)
post_pairs, post_m, _     = alias_pairs(NLJ, NLTOP)

parent = {}
def find(x):
    parent.setdefault(x, x)
    while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
    return x
def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb: parent[ra] = rb
for a, b in pre_pairs + post_pairs: union(a, b)

rtl_state_bits = {}
for cname, c in pre_m['cells'].items():
    if 'dff' not in c['type'].lower(): continue
    for b in c['connections'].get('Q', []):
        if isinstance(b, int):
            for nm in pre_b2n.get(b, []): rtl_state_bits[nm] = True

rtl_src = open(RTLV).read()
declared = set(re.findall(r'^\s*reg\s*(?:\[[^\]]*\]\s*)?(\w+)', rtl_src, re.M))

def score(nm):
    n = nm[0]; s = 0
    base = re.sub(r'\[\d+\]$', '', n)
    if base in declared: s += 200
    if nm in rtl_state_bits: s += 100
    if n.endswith('_o'): s -= 20
    return s

cls = collections.defaultdict(list)
for k in list(parent.keys()): cls[find(k)].append(k)
canon = {}
for root, members in cls.items():
    best = max(members, key=score)
    for mem in members: canon[mem] = best

src = open(NLV).read()
inst_re = re.compile(r'\b(DFFX1|DFFRX1)\s+(\S+)\s*\((.*?)\);', re.S)
conn_re = re.compile(r'\.(\w+)\(\s*(.*?)\s*\)')
def parse_q(q):
    q = q.strip()
    for pat, f in [
      (r'^\\(\w+)\[(\d+)\]\s+\[(\d+)\]$', lambda m:('%s[%s]'%(m.group(1),m.group(2)),int(m.group(3)))),
      (r'^\\(\w+)\[(\d+)\]\s*$',           lambda m:('%s[%s]'%(m.group(1),m.group(2)),0)),
      (r'^(\w+)\[(\d+)\]$',                lambda m:(m.group(1),int(m.group(2)))),
      (r'^(\w+)$',                         lambda m:(m.group(1),0))]:
        mm = re.match(pat, q)
        if mm: return f(mm)
    return None

entries = []
for cell, inst, body in inst_re.findall(src):
    conns = dict(conn_re.findall(body))
    p = parse_q(conns.get('Q',''))
    if not p: continue
    c = canon.get(p, p)
    entries.append({'inst':inst,'cell':cell,'has_reset':cell=='DFFRX1',
                    'nl_name':p[0],'nl_bit':p[1],'rtl_name':c[0],'rtl_bit':c[1],
                    'renamed':(c!=p)})
entries.sort(key=lambda e:(e['rtl_name'], e['rtl_bit']))
for i,e in enumerate(entries): e['idx']=i          # shared identity index

fp = {'rtl_sha':hashlib.sha256(open(RTLV,'rb').read()).hexdigest()[:16],
      'netlist_sha':hashlib.sha256(open(NLV,'rb').read()).hexdigest()[:16],
      'n_state':len(entries)}
json.dump({'fingerprint':fp,'elements':entries}, open(OUT,'w'), indent=1)
ren=sum(1 for e in entries if e['renamed']); res=sum(1 for e in entries if e['has_reset'])
print('state elements %d  | no reset %d (%.1f%%) | renamed %d (%.1f%%)'
      %(len(entries),len(entries)-res,100.0*(len(entries)-res)/len(entries),ren,100.0*ren/len(entries)))
g=collections.Counter(re.sub(r'\[\d+\]','[]',e['rtl_name']) for e in entries)
print('groups:', ', '.join('%s=%d'%(k,v) for k,v in sorted(g.items(),key=lambda x:-x[1])))
