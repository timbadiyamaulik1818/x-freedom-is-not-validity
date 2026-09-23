#!/usr/bin/env python3
"""
Build the canonical RTL <-> netlist state-element correspondence.

Two alias graphs are unioned:
  * pre-optimisation  (RTL reg name  ==  RTL wire/port name)
  * post-mapping      (netlist net   ==  netlist port)
A netlist flop's Q-net name is chased through the union until it reaches a
name that is the Q of an RTL-level sequential cell -- that is the canonical
RTL state bit.  Emits work/state_map.json.
"""
import json, re, collections

def alias_pairs(path):
    d = json.load(open(path))
    m = d['modules']['tinycpu']
    b2n = collections.defaultdict(list)
    for name, info in m['netnames'].items():
        if name.startswith('$'):
            continue
        for i, b in enumerate(info['bits']):
            if isinstance(b, int):
                b2n[b].append((name, i))
    pairs = []
    for b, names in b2n.items():
        for x in range(len(names)):
            for y in range(x + 1, len(names)):
                pairs.append((names[x], names[y]))
    return pairs, m

pre_pairs, pre_m = alias_pairs('syn/cpu_preopt.json')
post_pairs, post_m = alias_pairs('syn/cpu_netlist.json')

# union-find over (name, bit)
parent = {}
def find(x):
    parent.setdefault(x, x)
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x
def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb:
        parent[ra] = rb

for a, b in pre_pairs + post_pairs:
    union(a, b)

# RTL-level sequential elements: Q nets of $dff/$adff cells in the pre-opt design
rtl_state_bits = {}          # (name,bit) -> True
pre_nets = pre_m['netnames']
bit_owner = {}
for name, info in pre_nets.items():
    if name.startswith('$'):
        continue
    for i, b in enumerate(info['bits']):
        if isinstance(b, int):
            bit_owner.setdefault(b, []).append((name, i))

for cname, c in pre_m['cells'].items():
    if not c['type'].startswith('$'):
        continue
    if 'dff' not in c['type'].lower() and 'DFF' not in c['type']:
        continue
    q = c['connections'].get('Q', [])
    for b in q:
        if isinstance(b, int):
            for nm in bit_owner.get(b, []):
                rtl_state_bits[nm] = True

# Declared regs in the RTL source are the only legal deposit targets.
rtl_src = open('rtl/cpu.v').read()
declared_regs = set(re.findall(r'^\s*reg\s*(?:\[[^\]]*\]\s*)?(\w+)', rtl_src, re.M))
print('RTL declared regs     :', ' '.join(sorted(declared_regs)))

# preferred canonical name per class
def score(nm):
    n = nm[0]
    s = 0
    base = re.sub(r'\[\d+\]$', '', n)
    if base in declared_regs: s += 200      # declared reg -> depositable
    if nm in rtl_state_bits: s += 100          # is an actual RTL flop output
    if n in ('rf', 'dmem') or n.startswith('rf[') or n.startswith('dmem['): s += 50
    if n.endswith('_o'): s -= 20               # synthesis port name
    if n in ('imem_addr','pc_o'): s -= 10
    return s

cls = collections.defaultdict(list)
for k in list(parent.keys()):
    cls[find(k)].append(k)

canon = {}
for root, members in cls.items():
    best = max(members, key=score)
    for mem in members:
        canon[mem] = best

# now walk netlist flops
src = open('syn/cpu_netlist.v').read()
inst_re = re.compile(r'\b(DFFX1|DFFRX1)\s+(\S+)\s*\((.*?)\);', re.S)
conn_re = re.compile(r'\.(\w+)\(\s*(.*?)\s*\)')

def parse_q(q):
    q = q.strip()
    for pat, f in [
        (r'^\\(\w+)\[(\d+)\]\s+\[(\d+)\]$', lambda m: ('%s[%s]'%(m.group(1),m.group(2)), int(m.group(3)))),
        (r'^\\(\w+)\[(\d+)\]\s*$',           lambda m: ('%s[%s]'%(m.group(1),m.group(2)), 0)),
        (r'^(\w+)\[(\d+)\]$',                lambda m: (m.group(1), int(m.group(2)))),
        (r'^(\w+)$',                         lambda m: (m.group(1), 0)),
    ]:
        m = re.match(pat, q)
        if m: return f(m)
    return None

entries, unresolved = [], []
for cell, inst, body in inst_re.findall(src):
    conns = dict(conn_re.findall(body))
    p = parse_q(conns.get('Q',''))
    if not p:
        unresolved.append(conns.get('Q','')); continue
    key = p
    c = canon.get(key, key)
    entries.append({'inst': inst, 'cell': cell, 'has_reset': cell=='DFFRX1',
                    'q_net': conns.get('Q','').strip(),
                    'nl_name': p[0], 'nl_bit': p[1],
                    'rtl_name': c[0], 'rtl_bit': c[1],
                    'renamed': (c != key)})

# --- provenance fingerprint -------------------------------------------
# Binds the state map to the exact RTL source and netlist it was derived
# from.  A vector generated against one fingerprint must never be applied to
# a model with a different one.
import hashlib
def sha(path):
    return hashlib.sha256(open(path,'rb').read()).hexdigest()[:16]
fingerprint = {
    'rtl_sha':     sha('rtl/cpu.v'),
    'netlist_sha': sha('syn/cpu_netlist.v'),
    'lib_sha':     sha('lib/mocklib.lib'),
    'n_state':     len(entries),
    'state_sha':   hashlib.sha256(
        ''.join(sorted('%s/%s[%d]' % (e['inst'], e['rtl_name'], e['rtl_bit'])
                       for e in entries)).encode()).hexdigest()[:16],
}
json.dump({'fingerprint': fingerprint, 'elements': entries},
          open('work/state_map.json','w'), indent=1)
print('provenance fingerprint : rtl=%s netlist=%s state=%s'
      % (fingerprint['rtl_sha'], fingerprint['netlist_sha'], fingerprint['state_sha']))

ren = sum(1 for e in entries if e['renamed'])
print('mapped state elements : %d  (unresolved %d)' % (len(entries), len(unresolved)))
print('renamed by synthesis  : %d  (%.1f%%) -- naive name match would mis-seed these'
      % (ren, 100.0*ren/len(entries)))
print('\nrename classes:')
seen = collections.Counter()
for e in entries:
    if e['renamed']:
        seen[(re.sub(r'\[\d+\]','[]',e['nl_name']), re.sub(r'\[\d+\]','[]',e['rtl_name']))] += 1
for (a,b),c in seen.most_common():
    print('  netlist %-16s -> RTL %-12s  %3d bits' % (a,b,c))
print('\nRTL state groups covered:')
g = collections.Counter(re.sub(r'\[\d+\]','[]',e['rtl_name']) for e in entries)
for k,v in sorted(g.items(), key=lambda x:-x[1]):
    print('  %-14s %4d bits' % (k,v))
