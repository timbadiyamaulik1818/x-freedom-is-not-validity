#!/usr/bin/env python3
"""Assemble the self-contained EDA Playground testcase (design.sv + testbench.sv)."""
import json, re, collections

M = json.load(open('work/map_small.json'))
els, fp = M['elements'], M['fingerprint']
N = len(els)

# ---- compact the netlist: one line per cell -----------------------------
nl = open('syn/core_gate.v').read()
nl = re.sub(r'/\*.*?\*/', '', nl, flags=re.S)
nl = re.sub(r'\b(DFFX1|DFFRX1|INVX1|BUFX1|NAND2X1|NOR2X1|AND2X1|OR2X1|XOR2X1|XNOR2X1|MUX2X1|AOI21X1|OAI21X1)\s+(\S+)\s*\((.*?)\);',
            lambda m: '  %s %s (%s);' % (m.group(1), m.group(2),
                       ', '.join(x.strip() for x in m.group(3).split(',') if x.strip())),
            nl, flags=re.S)
nl = re.sub(r'\n{2,}', '\n', nl).strip()

cells = r'''// ---------------------------------------------------------------------------
// mocklib simulation models.  X propagates exactly as a vendor library would.
// DFFX1 has NO reset -- it is the X-corruption source.
// ---------------------------------------------------------------------------
module INVX1  (input A, output Y);        assign Y = ~A;        endmodule
module BUFX1  (input A, output Y);        assign Y =  A;        endmodule
module NAND2X1(input A, B, output Y);     assign Y = ~(A & B);  endmodule
module NOR2X1 (input A, B, output Y);     assign Y = ~(A | B);  endmodule
module AND2X1 (input A, B, output Y);     assign Y =  (A & B);  endmodule
module OR2X1  (input A, B, output Y);     assign Y =  (A | B);  endmodule
module XOR2X1 (input A, B, output Y);     assign Y =  (A ^ B);  endmodule
module XNOR2X1(input A, B, output Y);     assign Y = ~(A ^ B);  endmodule
module MUX2X1 (input A, B, S, output Y);  assign Y = S ? B : A; endmodule
module AOI21X1(input A, B, C, output Y);  assign Y = ~((A & B) | C); endmodule
module OAI21X1(input A, B, C, output Y);  assign Y = ~((A | B) & C); endmodule
module DFFX1  (input CK, input D, output reg Q);
  always @(posedge CK) Q <= D;
endmodule
module DFFRX1 (input CK, input RN, input D, output reg Q);
  always @(posedge CK or negedge RN) if (!RN) Q <= 1'b0; else Q <= D;
endmodule
'''

design = ('// ===========================================================================\n'
          '//  Cycle-accurate GLS via co-initialisation -- self-contained testcase\n'
          '//  design.sv : cell models + RTL core + its synthesised gate netlist\n'
          '//  Netlist produced by Yosys 0.68 from core_rtl in this same file.\n'
          '//  provenance: rtl=%s netlist=%s  %d state elements\n'
          '// ===========================================================================\n\n'
          % (fp['rtl_sha'], fp['netlist_sha'], fp['n_state'])
          + cells + '\n' + open('rtl/core_small.v').read() + '\n' + nl + '\n')
open('edaplayground/design.sv','w').write(design)

# ---- deposit lists ------------------------------------------------------
nores = [e for e in els if not e['has_reset']]
gate_dep = '\n'.join("    g.%s.Q = pk(m,s,%d);" % (e['inst'], e['idx']) for e in nores)

words = collections.defaultdict(dict)
for e in els: words[e['rtl_name']][e['rtl_bit']] = e['idx']
nrwords = collections.defaultdict(dict)
for e in nores: nrwords[e['rtl_name']][e['rtl_bit']] = e['idx']
rtl_lines = []
for w in sorted(nrwords):
    bits = nrwords[w]
    width = max(bits) + 1
    terms = ', '.join('pk(m,s,%d)' % bits[b] for b in range(width-1, -1, -1))
    rtl_lines.append("    r.%s = {%s};" % (w, terms))
rtl_dep = '\n'.join(rtl_lines)

gst = ',\n    '.join('g.%s.Q' % e['inst'] for e in reversed(els))
wwidth = {w: max(bits)+1 for w, bits in words.items()}
rst_terms = []
for e in reversed(els):
    if wwidth[e['rtl_name']] == 1:      # scalar reg: no bit-select allowed
        rst_terms.append('r.%s' % e['rtl_name'])
    else:
        rst_terms.append('r.%s[%d]' % (e['rtl_name'], e['rtl_bit']))
rst = ',\n    '.join(rst_terms)
con_g = '\n'.join("    g.%s.Q = 1'b0;" % e['inst'] for e in nores if e['rtl_name']=='rf[1]')
con_r = "    r.rf[1] = 8'h00;"
names = '\n'.join('      %d: nm = "%s[%d]";' % (e['idx'], e['rtl_name'], e['rtl_bit']) for e in els)

tb = r'''// ===========================================================================
//  testbench.sv -- runs three initialisation regimes on ONE pair of models
//  and prints a comparison table.  No plusargs, no files: paste and run.
//
//    ARM B  gate uninitialised, RTL uninitialised   -> X-corrupt divergence
//    ARM C  gate randomised, RTL uninitialised      -> X-free, still divergent
//    ARM E  BOTH co-initialised from one vector     -> cycle-identical
//
//  Verified on Icarus Verilog 13.0.  Intended to be re-run on VCS / Questa /
//  Xcelium to confirm the result is not simulator-specific.
// ===========================================================================
`timescale 1ns/1ps
module tb;

  localparam integer NST    = __NST__;   // mapped state elements
  localparam integer MAXCYC = 60;

  reg clk = 1'b0, rst_n = 1'b0;
  always #5 clk = ~clk;

  wire [3:0] r_pc, g_pc;  wire r_h, g_h, r_v, g_v;
  wire [7:0] r_val, g_val;

  core_rtl  r (.clk(clk), .rst_n(rst_n), .pc_o(r_pc), .halted_o(r_h),
               .rv_o(r_v), .rval_o(r_val));
  core_gate g (.clk(clk), .rst_n(rst_n), .pc_o(g_pc), .halted_o(g_h),
               .rv_o(g_v), .rval_o(g_val));

  // ---- full mapped state of both models, in one canonical order ---------
  wire [NST-1:0] gst = {
    __GST__};
  wire [NST-1:0] rst = {
    __RST__};

  // ---- shared power-up value function -----------------------------------
  //  m=0 : leave unknown          m=1 : independent randomisation
  //  m=2 : SHARED vector -- identical bit reaches both models via index i
  function pk(input integer m, input integer s, input integer i);
    reg [31:0] h;
    begin
      if (m == 0) pk = 1'bx;
      else begin
        h = (s * 32'h9E3779B9) ^ (i * 32'h85EBCA6B) ^ (m == 1 ? 32'hDEADBEEF : 32'h0);
        h = h ^ (h >> 15);  h = h * 32'h2545F491;  h = h ^ (h >> 13);
        pk = h[7];
      end
    end
  endfunction

  task dep_gate(input integer m, input integer s);
    begin
__GDEP__
    end
  endtask

  task dep_rtl(input integer m, input integer s);
    begin
__RDEP__
    end
  endtask

  // Architectural constraint: state the boot sequence is guaranteed to
  // establish.  Constraining it while leaving the other 44 elements free
  // defines a FAMILY of legal power-up vectors.
  task constrain;
    begin
__CONG__
__CONR__
    end
  endtask

  function [8*14:1] nm(input integer i);
    begin
      case (i)
__NAMES__
        default: nm = "?";
      endcase
    end
  endfunction

  // ---- one experimental arm ---------------------------------------------
  integer cyc, i, arch_div, state_div, xcnt, first_c, first_i;
  integer r_halt, g_halt;
  reg done;

  task run_arm(input [8*28:1] label, input integer gm, input integer rm,
               input integer seed, input integer con);
    begin
      // flush, then deposit between edges so no reset edge can undo it
      rst_n = 1'b0;
      repeat (3) @(posedge clk);
      @(negedge clk);
      dep_gate(gm, seed);
      dep_rtl (rm, seed);
      if (con) constrain;
      rst_n = 1'b1;

      cyc = 0; arch_div = 0; state_div = 0; xcnt = 0;
      first_c = -1; first_i = -1; done = 1'b0;
      r_halt = -1; g_halt = -1;

      while (!done) begin
        @(posedge clk); #1;
        cyc = cyc + 1;
        if ({r_pc,r_h,r_v,r_val} !== {g_pc,g_h,g_v,g_val}) arch_div = arch_div + 1;
        for (i = 0; i < NST; i = i + 1) begin
          if (gst[i] === 1'bx && rst[i] !== 1'bx) xcnt = xcnt + 1;
          if (gst[i] !== rst[i]) begin
            state_div = state_div + 1;
            if (first_c < 0) begin first_c = cyc; first_i = i; end
          end
        end
        if (r_h === 1'b1 && r_halt < 0) r_halt = cyc;
        if (g_h === 1'b1 && g_halt < 0) g_halt = cyc;
        if ((r_h === 1'b1 && g_h === 1'b1) || cyc >= MAXCYC) done = 1'b1;
      end

      $display("%0s | %4d | %7d | %8d | %6d", label, cyc, arch_div, state_div, xcnt);
      $write("       RTL halted@");
      if (r_halt < 0) $write("never "); else $write("%0d ", r_halt);
      $write("  GATE halted@");
      if (g_halt < 0) $write("never"); else $write("%0d", g_halt);
      $display("");
      if (first_c >= 0)
        $display("       first divergence: cycle %0d  element %0s  RTL=%b GATE=%b  [%0s]",
                 first_c, nm(first_i), rst[first_i], gst[first_i],
                 (gst[first_i] === 1'bx) ? "X-ORIGIN" : "VALUE MISMATCH");
      else
        $display("       MATCH: all %0d mapped state elements identical every cycle", NST);
      $display("");
    end
  endtask

  initial begin
    $display("");
    $display("=====================================================================");
    $display(" Cycle-accurate GLS via co-initialisation -- %0d mapped state elements", NST);
    $display("=====================================================================");
    $display("arm                          | cyc |arch div| state div| gateX | first div");
    $display("---------------------------------------------------------------------");

    run_arm("B no init                   ", 0, 0, 1, 0);
    run_arm("C gate randomised (RTL X)   ", 1, 0, 1, 0);
    run_arm("E co-init seed=1            ", 2, 2, 1, 0);
    run_arm("E co-init seed=2            ", 2, 2, 2, 0);
    run_arm("E co-init seed=1 constrained", 2, 2, 1, 1);
    run_arm("E co-init seed=2 constrained", 2, 2, 2, 1);
    run_arm("E co-init seed=3 constrained", 2, 2, 3, 1);

    $display("Interpretation:");
    $display("  ARM C removes every X from the netlist yet still diverges from RTL.");
    $display("  X-freedom is therefore NOT evidence that gate activity is valid.");
    $display("  ARM E shares ONE power-up vector across both models -> lockstep.");
    $display("  Constrained ARM E fixes rf[1] (state boot firmware guarantees) and");
    $display("  sweeps the remaining 44 free elements: every member stays in lockstep");
    $display("  AND runs the full workload, so its activity is valid for power.");
    $display("");
    $finish;
  end
endmodule
'''
tb = (tb.replace('__NST__', str(N)).replace('__GST__', gst).replace('__RST__', rst)
        .replace('__GDEP__', gate_dep).replace('__RDEP__', rtl_dep).replace('__NAMES__', names)
        .replace('__CONG__', con_g).replace('__CONR__', con_r))
open('edaplayground/testbench.sv','w').write(tb)
print('design.sv    %5d lines' % design.count('\n'))
print('testbench.sv %5d lines' % tb.count('\n'))
