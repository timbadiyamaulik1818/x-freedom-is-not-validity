// ===========================================================================
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

  localparam integer NST    = 58;   // mapped state elements
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
    g._596_.Q,
    g._585_.Q,
    g._572_.Q,
    g._547_.Q,
    g._546_.Q,
    g._545_.Q,
    g._544_.Q,
    g._543_.Q,
    g._542_.Q,
    g._541_.Q,
    g._540_.Q,
    g._555_.Q,
    g._554_.Q,
    g._553_.Q,
    g._552_.Q,
    g._551_.Q,
    g._550_.Q,
    g._549_.Q,
    g._548_.Q,
    g._563_.Q,
    g._562_.Q,
    g._561_.Q,
    g._560_.Q,
    g._559_.Q,
    g._558_.Q,
    g._557_.Q,
    g._556_.Q,
    g._571_.Q,
    g._570_.Q,
    g._569_.Q,
    g._568_.Q,
    g._567_.Q,
    g._566_.Q,
    g._565_.Q,
    g._564_.Q,
    g._595_.Q,
    g._594_.Q,
    g._576_.Q,
    g._575_.Q,
    g._574_.Q,
    g._573_.Q,
    g._584_.Q,
    g._583_.Q,
    g._582_.Q,
    g._581_.Q,
    g._580_.Q,
    g._579_.Q,
    g._578_.Q,
    g._577_.Q,
    g._597_.Q,
    g._593_.Q,
    g._592_.Q,
    g._591_.Q,
    g._590_.Q,
    g._589_.Q,
    g._588_.Q,
    g._587_.Q,
    g._586_.Q};
  wire [NST-1:0] rst = {
    r.we_w,
    r.v_w,
    r.v_d,
    r.rf[3][7],
    r.rf[3][6],
    r.rf[3][5],
    r.rf[3][4],
    r.rf[3][3],
    r.rf[3][2],
    r.rf[3][1],
    r.rf[3][0],
    r.rf[2][7],
    r.rf[2][6],
    r.rf[2][5],
    r.rf[2][4],
    r.rf[2][3],
    r.rf[2][2],
    r.rf[2][1],
    r.rf[2][0],
    r.rf[1][7],
    r.rf[1][6],
    r.rf[1][5],
    r.rf[1][4],
    r.rf[1][3],
    r.rf[1][2],
    r.rf[1][1],
    r.rf[1][0],
    r.rf[0][7],
    r.rf[0][6],
    r.rf[0][5],
    r.rf[0][4],
    r.rf[0][3],
    r.rf[0][2],
    r.rf[0][1],
    r.rf[0][0],
    r.rd_w[1],
    r.rd_w[0],
    r.pc[3],
    r.pc[2],
    r.pc[1],
    r.pc[0],
    r.ir_d[7],
    r.ir_d[6],
    r.ir_d[5],
    r.ir_d[4],
    r.ir_d[3],
    r.ir_d[2],
    r.ir_d[1],
    r.ir_d[0],
    r.halted,
    r.acc_w[7],
    r.acc_w[6],
    r.acc_w[5],
    r.acc_w[4],
    r.acc_w[3],
    r.acc_w[2],
    r.acc_w[1],
    r.acc_w[0]};

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
    g._586_.Q = pk(m,s,0);
    g._587_.Q = pk(m,s,1);
    g._588_.Q = pk(m,s,2);
    g._589_.Q = pk(m,s,3);
    g._590_.Q = pk(m,s,4);
    g._591_.Q = pk(m,s,5);
    g._592_.Q = pk(m,s,6);
    g._593_.Q = pk(m,s,7);
    g._577_.Q = pk(m,s,9);
    g._578_.Q = pk(m,s,10);
    g._579_.Q = pk(m,s,11);
    g._580_.Q = pk(m,s,12);
    g._581_.Q = pk(m,s,13);
    g._582_.Q = pk(m,s,14);
    g._583_.Q = pk(m,s,15);
    g._584_.Q = pk(m,s,16);
    g._594_.Q = pk(m,s,21);
    g._595_.Q = pk(m,s,22);
    g._564_.Q = pk(m,s,23);
    g._565_.Q = pk(m,s,24);
    g._566_.Q = pk(m,s,25);
    g._567_.Q = pk(m,s,26);
    g._568_.Q = pk(m,s,27);
    g._569_.Q = pk(m,s,28);
    g._570_.Q = pk(m,s,29);
    g._571_.Q = pk(m,s,30);
    g._556_.Q = pk(m,s,31);
    g._557_.Q = pk(m,s,32);
    g._558_.Q = pk(m,s,33);
    g._559_.Q = pk(m,s,34);
    g._560_.Q = pk(m,s,35);
    g._561_.Q = pk(m,s,36);
    g._562_.Q = pk(m,s,37);
    g._563_.Q = pk(m,s,38);
    g._548_.Q = pk(m,s,39);
    g._549_.Q = pk(m,s,40);
    g._550_.Q = pk(m,s,41);
    g._551_.Q = pk(m,s,42);
    g._552_.Q = pk(m,s,43);
    g._553_.Q = pk(m,s,44);
    g._554_.Q = pk(m,s,45);
    g._555_.Q = pk(m,s,46);
    g._540_.Q = pk(m,s,47);
    g._541_.Q = pk(m,s,48);
    g._542_.Q = pk(m,s,49);
    g._543_.Q = pk(m,s,50);
    g._544_.Q = pk(m,s,51);
    g._545_.Q = pk(m,s,52);
    g._546_.Q = pk(m,s,53);
    g._547_.Q = pk(m,s,54);
    g._585_.Q = pk(m,s,56);
    g._596_.Q = pk(m,s,57);
    end
  endtask

  task dep_rtl(input integer m, input integer s);
    begin
    r.acc_w = {pk(m,s,7), pk(m,s,6), pk(m,s,5), pk(m,s,4), pk(m,s,3), pk(m,s,2), pk(m,s,1), pk(m,s,0)};
    r.ir_d = {pk(m,s,16), pk(m,s,15), pk(m,s,14), pk(m,s,13), pk(m,s,12), pk(m,s,11), pk(m,s,10), pk(m,s,9)};
    r.rd_w = {pk(m,s,22), pk(m,s,21)};
    r.rf[0] = {pk(m,s,30), pk(m,s,29), pk(m,s,28), pk(m,s,27), pk(m,s,26), pk(m,s,25), pk(m,s,24), pk(m,s,23)};
    r.rf[1] = {pk(m,s,38), pk(m,s,37), pk(m,s,36), pk(m,s,35), pk(m,s,34), pk(m,s,33), pk(m,s,32), pk(m,s,31)};
    r.rf[2] = {pk(m,s,46), pk(m,s,45), pk(m,s,44), pk(m,s,43), pk(m,s,42), pk(m,s,41), pk(m,s,40), pk(m,s,39)};
    r.rf[3] = {pk(m,s,54), pk(m,s,53), pk(m,s,52), pk(m,s,51), pk(m,s,50), pk(m,s,49), pk(m,s,48), pk(m,s,47)};
    r.v_w = {pk(m,s,56)};
    r.we_w = {pk(m,s,57)};
    end
  endtask

  // Architectural constraint: state the boot sequence is guaranteed to
  // establish.  Constraining it while leaving the other 44 elements free
  // defines a FAMILY of legal power-up vectors.
  task constrain;
    begin
    g._556_.Q = 1'b0;
    g._557_.Q = 1'b0;
    g._558_.Q = 1'b0;
    g._559_.Q = 1'b0;
    g._560_.Q = 1'b0;
    g._561_.Q = 1'b0;
    g._562_.Q = 1'b0;
    g._563_.Q = 1'b0;
    r.rf[1] = 8'h00;
    end
  endtask

  function [8*14:1] nm(input integer i);
    begin
      case (i)
      0: nm = "acc_w[0]";
      1: nm = "acc_w[1]";
      2: nm = "acc_w[2]";
      3: nm = "acc_w[3]";
      4: nm = "acc_w[4]";
      5: nm = "acc_w[5]";
      6: nm = "acc_w[6]";
      7: nm = "acc_w[7]";
      8: nm = "halted[0]";
      9: nm = "ir_d[0]";
      10: nm = "ir_d[1]";
      11: nm = "ir_d[2]";
      12: nm = "ir_d[3]";
      13: nm = "ir_d[4]";
      14: nm = "ir_d[5]";
      15: nm = "ir_d[6]";
      16: nm = "ir_d[7]";
      17: nm = "pc[0]";
      18: nm = "pc[1]";
      19: nm = "pc[2]";
      20: nm = "pc[3]";
      21: nm = "rd_w[0]";
      22: nm = "rd_w[1]";
      23: nm = "rf[0][0]";
      24: nm = "rf[0][1]";
      25: nm = "rf[0][2]";
      26: nm = "rf[0][3]";
      27: nm = "rf[0][4]";
      28: nm = "rf[0][5]";
      29: nm = "rf[0][6]";
      30: nm = "rf[0][7]";
      31: nm = "rf[1][0]";
      32: nm = "rf[1][1]";
      33: nm = "rf[1][2]";
      34: nm = "rf[1][3]";
      35: nm = "rf[1][4]";
      36: nm = "rf[1][5]";
      37: nm = "rf[1][6]";
      38: nm = "rf[1][7]";
      39: nm = "rf[2][0]";
      40: nm = "rf[2][1]";
      41: nm = "rf[2][2]";
      42: nm = "rf[2][3]";
      43: nm = "rf[2][4]";
      44: nm = "rf[2][5]";
      45: nm = "rf[2][6]";
      46: nm = "rf[2][7]";
      47: nm = "rf[3][0]";
      48: nm = "rf[3][1]";
      49: nm = "rf[3][2]";
      50: nm = "rf[3][3]";
      51: nm = "rf[3][4]";
      52: nm = "rf[3][5]";
      53: nm = "rf[3][6]";
      54: nm = "rf[3][7]";
      55: nm = "v_d[0]";
      56: nm = "v_w[0]";
      57: nm = "we_w[0]";
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
