#!/usr/bin/env python3
"""
Build the RTL<->netlist state correspondence map from a formal equivalence
checker's matched-state-point report.

For a production core this is STRONGLY preferred over name heuristics: the LEC
already solved this problem, it survives retiming and re-encoding, and it tells
you about unmatched points instead of silently guessing.

  Formality :  match
               report_matched_points -point_type DFF > matched.rpt
  Conformal :  report mapped points -type DFF > matched.rpt

Both emit lines pairing a golden (RTL) point with a revised (netlist) point.
Adjust PAT below if your tool's column layout differs -- print a few lines of
your report first and check.

usage: map_from_lec.py <matched.rpt> <out_map.json> [--rtl-inst r] [--gate-inst g]
"""
import re, json, sys, hashlib, collections

rpt, out = sys.argv[1], sys.argv[2]
args = sys.argv[3:]
def opt(flag, dflt):
    return args[args.index(flag)+1] if flag in args else dflt
RI, GI = opt('--rtl-inst', 'r'), opt('--gate-inst', 'g')

# Two golden/revised object paths on one line, each possibly bit-selected.
PAT = re.compile(r'^\s*(?:\d+\s+)?[\w\-]*\s*'
                 r'(?P<g>[\w\$\\\./\[\]]+)\s+'
                 r'(?P<r>[\w\$\\\./\[\]]+)\s*$')

pairs, skipped = [], 0
for line in open(rpt):
    if not line.strip() or line.lstrip().startswith(('#', '-', '=')):
        continue
    m = PAT.match(line.rstrip())
    if not m:
        skipped += 1
        continue
    pairs.append((m.group('g'), m.group('r')))

def norm(p):
    p = p.strip().lstrip('\\')
    p = p.replace('/', '.')
    return p

els = []
for i, (gpt, rpt_) in enumerate(pairs):
    els.append({'idx': i, 'rtl_path': norm(gpt), 'gate_path': norm(rpt_)})

fp = {'report_sha': hashlib.sha256(open(rpt, 'rb').read()).hexdigest()[:16],
      'n_state': len(els)}
json.dump({'fingerprint': fp, 'rtl_inst': RI, 'gate_inst': GI,
           'elements': els}, open(out, 'w'), indent=1)
print('matched state points : %d   (unparsed lines: %d)' % (len(els), skipped))
if skipped:
    print('  >> if this is large, your report layout differs -- adjust PAT')
print('fingerprint          : %s' % fp['report_sha'])
