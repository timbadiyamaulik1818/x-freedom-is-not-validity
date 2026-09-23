#!/usr/bin/env python3
"""Assemble the benchmark program into prog.hex (one 32-bit word per line)."""
OPS = dict(NOP=0, ADD=1, SUB=2, AND=3, OR=4, XOR=5, SHL=6, SHR=7,
           LI=8, BNZ=9, LD=10, ST=11, HALT=15)

def enc(op, rd=0, rs1=0, rs2=0, imm=0):
    return ((OPS[op] & 0xF) << 28) | ((rd & 7) << 25) | ((rs1 & 7) << 22) \
         | ((rs2 & 7) << 19) | (imm & 0xFFFF)

# r1=counter r2=acc r3=addend r4=1 r5,r6=scratch r7=mem addr
#
# The program opens with a boot-style guard that branches on r5 BEFORE any
# instruction has written it.  The register file has no reset, so r5 is
# uninitialised.  This is the canonical gate-level divergence source:
#   RTL   : `taken` evaluates to X, `if (taken)` takes the else path
#           (X-optimism) -- RTL runs the fall-through path deterministically.
#   GATES : the same select is a mux, X reaches the PC (X-pessimism) and
#           execution collapses.
prog = [
    enc('BNZ',       rs1=5, imm=20),  # 0  boot guard on UNINITIALISED r5
    enc('NOP'),                       # 1  delay slot
    enc('LI',  rd=1, imm=12),         # 2  r1 = 12
    enc('LI',  rd=2, imm=0),          # 3  r2 = 0
    enc('LI',  rd=3, imm=0x3F5),      # 4  r3 = 1013
    enc('LI',  rd=4, imm=1),          # 5  r4 = 1
    enc('LI',  rd=7, imm=0),          # 6  r7 = 0
    # ---- loop @7 ----
    enc('ADD', rd=2, rs1=2, rs2=3),   # 7  r2 += r3
    enc('XOR', rd=5, rs1=2, rs2=1),   # 8  r5 = r2 ^ r1
    enc('SHL', rd=6, rs1=2, rs2=4),   # 9  r6 = r2 << 1
    enc('ST',        rs1=7, rs2=5),   # 10 dmem[r7] = r5
    enc('SUB', rd=1, rs1=1, rs2=4),   # 11 r1 -= 1
    enc('ADD', rd=7, rs1=7, rs2=4),   # 12 r7 += 1
    enc('BNZ',       rs1=1, imm=7),   # 13 if r1 != 0 goto 7
    enc('NOP'),                       # 14 delay slot
    enc('LD',  rd=6, rs1=4),          # 15 r6 = dmem[r4]
    enc('XOR', rd=5, rs1=6, rs2=2),   # 16 r5 = r6 ^ r2
    enc('HALT'),                      # 17
]
prog += [enc('NOP')] * (20 - len(prog))
prog += [
    enc('LI',  rd=1, imm=99),         # 20 "error" path
    enc('HALT'),                      # 21
]
prog += [enc('NOP')] * (64 - len(prog))
with open('tb/prog.hex', 'w') as f:
    for w in prog:
        f.write('%08x\n' % w)
print('wrote tb/prog.hex : %d words, %d real instructions' % (len(prog), 22))
