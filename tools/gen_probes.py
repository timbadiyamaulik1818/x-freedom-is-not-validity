#!/usr/bin/env python3
"""Emit per-cycle state probes for both models, in one canonical order."""
import json, collections
_m = json.load(open('work/state_map.json'))
smap = _m['elements']
order = sorted(smap, key=lambda e: (e['rtl_name'], e['rtl_bit']))
json.dump([[e['rtl_name'], e['rtl_bit']] for e in order], open('work/probe_order.json','w'))

# GLS: concatenate the 680 flop Q pins in canonical order
with open('work/probe_gls.vh','w') as f:
    f.write('wire [%d:0] _st = {\n' % (len(order)-1))
    f.write(',\n'.join('  dut.%s.Q' % e['inst'] for e in order))
    f.write('};\n')

# RTL: dump whole storage words; Python re-slices them to bits
words = sorted({e['rtl_name'] for e in smap})
width = collections.defaultdict(int)
for e in smap: width[e['rtl_name']] = max(width[e['rtl_name']], e['rtl_bit']+1)
with open('work/probe_rtl.vh','w') as f:
    f.write('  $fwrite(pf, "%0d", cyc);\n')
    for w in words:
        f.write('  $fwrite(pf, " %s=%%b", dut.%s);\n' % (w, w))
    f.write('  $fwrite(pf, "\\n");\n')
json.dump({w: width[w] for w in words}, open('work/probe_widths.json','w'))

# Snapshot probe: same canonical word list, binary radix, written to the
# snapshot file handle.  Used by the checkpoint-transplant flow.
with open('work/probe_snap.vh','w') as f:
    for w in words:
        f.write('      $fwrite(sf, "%s %%b\\n", dut.%s);\n' % (w, w))
print('probes for %d flops / %d storage words (incl. snapshot probe)' % (len(order), len(words)))
