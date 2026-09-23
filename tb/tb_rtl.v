`timescale 1ns/1ps
// Golden RTL testbench.  Produces (a) a per-cycle architectural trace and
// (b) a full state snapshot at SNAP_CYCLE used to seed gate-level runs.
module tb;
  reg clk = 1'b0, rst_n = 1'b0;
  wire [5:0]  imem_addr;
  wire [31:0] imem_data;
  wire [31:0] pc_o, retire_pc_o, retire_val_o;
  wire        halted_o, retire_v_o;
  wire [3:0]  retire_op_o;
  wire [2:0]  retire_rd_o;

  reg [31:0] rom [0:63];
  assign imem_data = rom[imem_addr];

  tinycpu dut (.clk(clk), .rst_n(rst_n), .imem_addr(imem_addr),
               .imem_data(imem_data), .pc_o(pc_o), .halted_o(halted_o),
               .retire_v_o(retire_v_o), .retire_pc_o(retire_pc_o),
               .retire_op_o(retire_op_o), .retire_rd_o(retire_rd_o),
               .retire_val_o(retire_val_o));

  always #5 clk = ~clk;

  integer tf, sf, pf, cyc, i;
  reg [1023:0] trace_file, snap_file, vcd_file;
  integer snap_cycle, max_cycle;

  initial begin
    if (!$value$plusargs("trace=%s", trace_file)) trace_file = "work/rtl.trace";
    if (!$value$plusargs("snap=%s",  snap_file))  snap_file  = "work/rtl.snap";
    if (!$value$plusargs("vcd=%s",   vcd_file))   vcd_file   = "work/rtl.vcd";
    if (!$value$plusargs("snapcyc=%d", snap_cycle)) snap_cycle = 2;
    if (!$value$plusargs("maxcyc=%d",  max_cycle))  max_cycle  = 400;

`ifdef INIT_DEPOSIT
    `include "work/deposit_rtl.vh"
`endif

    $readmemh("tb/prog.hex", rom);
    $dumpfile(vcd_file);
    $dumpvars(0, tb);
    tf = $fopen(trace_file, "w");
`ifndef NO_PROBE
    pf = $fopen({trace_file, ".state"}, "w");
`endif

    cyc = 0;
    repeat (4) @(posedge clk);
    rst_n <= 1'b1;                       // release reset

    forever begin
      @(posedge clk);
      #1;                                // settle
      cyc = cyc + 1;
      $fwrite(tf, "%0d %h %b %b %h %h %h %h\n", cyc, pc_o, halted_o,
              retire_v_o, retire_pc_o, retire_op_o, retire_rd_o, retire_val_o);
`ifndef NO_PROBE
`include "work/probe_rtl.vh"
`endif
      if (cyc == snap_cycle) dump_snapshot;
      if (halted_o || cyc >= max_cycle) begin
        $fclose(tf);
`ifndef NO_PROBE
        $fclose(pf);
`endif
        $display("RTL: finished at cycle %0d halted=%b", cyc, halted_o);
        $finish;
      end
    end
  end

  // Full architectural + microarchitectural state snapshot.
  task dump_snapshot;
    begin
      sf = $fopen(snap_file, "w");
      $fwrite(sf, "# cycle %0d\n", cyc);
`include "work/probe_snap.vh"
      $fclose(sf);
      $display("RTL: snapshot written at cycle %0d", cyc);
    end
  endtask
endmodule
