`timescale 1ns/1ps
// Gate-level testbench.  Identical stimulus and trace format to tb_rtl.v so
// the two traces can be compared cycle-for-cycle.
//   -DINIT_NONE     : leave non-resettable flops at 1'bx  (baseline GLS)
//   -DINIT_RANDOM   : simulator-style independent randomisation (+vcs+initreg)
//   -DINIT_DEPOSIT  : co-initialise from the shared power-up state vector
module tb;
`ifdef INIT_CKPT
  reg clk = 1'b0, rst_n = 1'b1;
`else
  reg clk = 1'b0, rst_n = 1'b0;
`endif
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

  integer tf, pf, cyc;
`include "work/probe_gls.vh"
  reg [1023:0] trace_file, vcd_file;
  integer max_cycle, iseed;

  initial begin
    if (!$value$plusargs("trace=%s", trace_file)) trace_file = "work/gls.trace";
    if (!$value$plusargs("vcd=%s",   vcd_file))   vcd_file   = "work/gls.vcd";
    if (!$value$plusargs("maxcyc=%d", max_cycle)) max_cycle  = 400;
    if (!$value$plusargs("iseed=%d",  iseed))     iseed      = 1;

`ifdef INIT_RANDOM
    `include "work/initrandom_gls.vh"
`endif
`ifdef INIT_DEPOSIT
    `include "work/deposit_gls.vh"
`endif
`ifdef INIT_CKPT
    `include "work/deposit_ckpt.vh"
`endif

    $readmemh("tb/prog.hex", rom);
    $dumpfile(vcd_file);
    $dumpvars(0, tb);
    tf = $fopen(trace_file, "w");
`ifndef NO_PROBE
    pf = $fopen({trace_file, ".state"}, "w");
`endif

`ifdef INIT_CKPT
    // checkpoint transplant: reset already done, resume from the RTL cycle
    `include "work/ckpt_cycle.vh"
    rst_n = 1'b1;
`else
    cyc = 0;
    repeat (4) @(posedge clk);
    rst_n <= 1'b1;
`endif

    forever begin
      @(posedge clk);
      #1;
      cyc = cyc + 1;
      $fwrite(tf, "%0d %h %b %b %h %h %h %h\n", cyc, pc_o, halted_o,
              retire_v_o, retire_pc_o, retire_op_o, retire_rd_o, retire_val_o);
`ifndef NO_PROBE
      $fwrite(pf, "%0d %b\n", cyc, _st);
`endif
      if (halted_o || cyc >= max_cycle) begin
        $fclose(tf);
`ifndef NO_PROBE
        $fclose(pf);
`endif
        $display("GLS: finished at cycle %0d halted=%b", cyc, halted_o);
        $finish;
      end
    end
  end
endmodule
