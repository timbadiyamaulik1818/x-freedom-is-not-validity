// Minimal core exhibiting the RTL-optimism / gate-pessimism divergence.
// Reset: pc, v_d, halted.   NOT reset: register file, ir_d, v_w, acc_w.
module core_rtl (
  input  wire       clk,
  input  wire       rst_n,
  output wire [3:0] pc_o,
  output wire       halted_o,
  output wire       rv_o,      // retire valid
  output wire [7:0] rval_o     // retired value
);
  localparam OP_LI=3'd0, OP_ADD=3'd1, OP_XOR=3'd2, OP_BNZ=3'd3,
             OP_SHL=3'd4, OP_SUB=3'd5, OP_NOP=3'd6, OP_HALT=3'd7;

  reg [7:0] rf [0:3];          // NOT reset
  reg [3:0] pc;                // reset
  reg       halted, v_d;       // reset
  reg       v_w;               // NOT reset
  reg [7:0] ir_d;              // NOT reset
  reg [7:0] acc_w;             // NOT reset
  reg [1:0] rd_w;              // NOT reset
  reg       we_w;              // NOT reset

  // instruction ROM: {op[2:0], rd[1:0], rs[1:0], imm-ish[0]}
  reg [7:0] rom [0:15];
  initial begin
    rom[ 0] = {OP_BNZ, 2'd0, 2'd1, 1'b1};  // branch if rf[1]!=0  -> pc 12   (rf[1] UNINITIALISED)
    rom[ 1] = {OP_NOP, 2'd0, 2'd0, 1'b0};  // delay slot
    rom[ 2] = {OP_LI , 2'd1, 2'd0, 1'b1};  // rf[1] = 3
    rom[ 3] = {OP_LI , 2'd2, 2'd0, 1'b0};  // rf[2] = 2
    rom[ 4] = {OP_ADD, 2'd3, 2'd1, 1'b0};  // rf[3] = rf[3] + rf[1]
    rom[ 5] = {OP_XOR, 2'd2, 2'd1, 1'b0};  // rf[2] ^= rf[1]
    rom[ 6] = {OP_SHL, 2'd3, 2'd3, 1'b0};  // rf[3] <<= 1
    rom[ 7] = {OP_SUB, 2'd1, 2'd2, 1'b0};  // rf[1] -= rf[2]
    rom[ 8] = {OP_ADD, 2'd2, 2'd3, 1'b0};
    rom[ 9] = {OP_XOR, 2'd3, 2'd2, 1'b0};
    rom[10] = {OP_HALT,2'd0, 2'd0, 1'b0};
    rom[11] = {OP_NOP, 2'd0, 2'd0, 1'b0};
    rom[12] = {OP_LI , 2'd3, 2'd0, 1'b1};  // "error" path
    rom[13] = {OP_HALT,2'd0, 2'd0, 1'b0};
    rom[14] = {OP_NOP, 2'd0, 2'd0, 1'b0};
    rom[15] = {OP_NOP, 2'd0, 2'd0, 1'b0};
  end

  wire [7:0] insn = rom[pc];
  wire [2:0] op_d = ir_d[7:5];
  wire [1:0] rd_d = ir_d[4:3];
  wire [1:0] rs_d = ir_d[2:1];
  wire       im_d = ir_d[0];

  wire [7:0] rf_rs = rf[rs_d];
  wire       fwd   = v_w & we_w & (rd_w == rs_d);
  wire [7:0] opa   = fwd ? acc_w : rf_rs;
  wire [7:0] rf_rd = rf[rd_d];
  wire       fwdd  = v_w & we_w & (rd_w == rd_d);
  wire [7:0] opd   = fwdd ? acc_w : rf_rd;

  reg [7:0] alu;
  always @* begin
    case (op_d)                              // X-optimistic in RTL
      OP_LI : alu = im_d ? 8'd3 : 8'd2;
      OP_ADD: alu = opd + opa;
      OP_XOR: alu = opd ^ opa;
      OP_SHL: alu = opd << 1;
      OP_SUB: alu = opd - opa;
      default: alu = opd;
    endcase
  end

  wire writes = v_d & ((op_d==OP_LI)|(op_d==OP_ADD)|(op_d==OP_XOR)|
                       (op_d==OP_SHL)|(op_d==OP_SUB));
  wire taken  = v_d & (op_d==OP_BNZ) & (opa != 8'd0);   // <- X here in gates
  wire dohalt = v_d & (op_d==OP_HALT);

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      pc <= 4'd0; halted <= 1'b0; v_d <= 1'b0;
    end else if (!halted) begin
      v_d <= 1'b1;
      if (dohalt)     halted <= 1'b1;
      else if (taken) pc <= 4'd12;
      else            pc <= pc + 4'd1;
    end
  end

  always @(posedge clk) begin
    ir_d  <= insn;
    v_w   <= v_d;
    acc_w <= alu;
    rd_w  <= rd_d;
    we_w  <= writes;
  end

  always @(posedge clk) if (v_w & we_w) rf[rd_w] <= acc_w;

  assign pc_o = pc; assign halted_o = halted;
  assign rv_o = v_w; assign rval_o = acc_w;
endmodule
