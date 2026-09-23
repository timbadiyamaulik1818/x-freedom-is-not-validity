// ---------------------------------------------------------------------------
// tinycpu : 3-stage pipelined 32-bit CPU used as the DUT for the
//           cycle-accurate GLS / power-activity experiments.
//
// Reset structure is deliberately realistic for an ASIC core:
//   *  RESET   : pc, stage valid bits, a small amount of control state
//   *  NO RESET: register file, data memory, and all pipeline datapath
//                registers (ir_d, opa_e, opb_e, alu_r_w, ...)
//
// That asymmetry is the whole point: it is what area/power-driven reset
// minimisation produces in a real core, and it is what makes gate-level
// simulation X-corrupt at time 0.
// ---------------------------------------------------------------------------
module tinycpu (
    input  wire        clk,
    input  wire        rst_n,
    output wire [5:0]  imem_addr,   // instruction fetch address (external ROM)
    input  wire [31:0] imem_data,   // instruction fetch data
    output wire [31:0] pc_o,
    output wire        halted_o,
    output wire        retire_v_o,   // an instruction retired this cycle
    output wire [31:0] retire_pc_o,  // its PC
    output wire [3:0]  retire_op_o,  // its opcode
    output wire [2:0]  retire_rd_o,  // its destination register
    output wire [31:0] retire_val_o  // the value written back
);

  // opcodes
  localparam OP_NOP  = 4'd0,  OP_ADD = 4'd1,  OP_SUB = 4'd2, OP_AND = 4'd3,
             OP_OR   = 4'd4,  OP_XOR = 4'd5,  OP_SHL = 4'd6, OP_SHR = 4'd7,
             OP_LI   = 4'd8,  OP_BNZ = 4'd9,  OP_LD  = 4'd10, OP_ST = 4'd11,
             OP_HALT = 4'd15;

  // ---------------- data memory : NOT reset -------------------------------
  reg [31:0] dmem [0:7];
  // ---------------- register file : NOT reset -----------------------------
  reg [31:0] rf [0:7];

  // ---------------- stage F : reset ---------------------------------------
  reg [31:0] pc;
  reg        halted;

  // ---------------- stage D : valid resets, datapath does NOT -------------
  reg        v_d;
  reg [31:0] ir_d;
  reg [31:0] pc_d;

  // ---------------- stage E/W : valid resets, datapath does NOT -----------
  reg        v_w;
  reg [31:0] alu_r_w;
  reg [2:0]  rd_w;
  reg        we_w;
  reg [31:0] pc_w;
  reg [3:0]  op_w;

  // decode of the D-stage instruction
  wire [3:0]  op_d  = ir_d[31:28];
  wire [2:0]  rd_d  = ir_d[27:25];
  wire [2:0]  rs1_d = ir_d[24:22];
  wire [2:0]  rs2_d = ir_d[21:19];
  wire [15:0] imm_d = ir_d[15:0];

  // register read + write-back forwarding
  wire [31:0] rf_rs1 = rf[rs1_d];
  wire [31:0] rf_rs2 = rf[rs2_d];
  wire fwd1 = v_w & we_w & (rd_w == rs1_d);
  wire fwd2 = v_w & we_w & (rd_w == rs2_d);
  wire [31:0] opa = fwd1 ? alu_r_w : rf_rs1;
  wire [31:0] opb = fwd2 ? alu_r_w : rf_rs2;

  // ALU
  reg [31:0] alu_r;
  always @* begin
    case (op_d)
      OP_ADD : alu_r = opa + opb;
      OP_SUB : alu_r = opa - opb;
      OP_AND : alu_r = opa & opb;
      OP_OR  : alu_r = opa | opb;
      OP_XOR : alu_r = opa ^ opb;
      OP_SHL : alu_r = opa << opb[4:0];
      OP_SHR : alu_r = opa >> opb[4:0];
      OP_LI  : alu_r = {{16{imm_d[15]}}, imm_d};
      OP_LD  : alu_r = dmem[opa[2:0]];
      default: alu_r = opa;
    endcase
  end

  wire writes_rd = v_d & ((op_d==OP_ADD)|(op_d==OP_SUB)|(op_d==OP_AND)|
                          (op_d==OP_OR )|(op_d==OP_XOR)|(op_d==OP_SHL)|
                          (op_d==OP_SHR)|(op_d==OP_LI )|(op_d==OP_LD ));

  wire taken = v_d & (op_d == OP_BNZ) & (opa != 32'd0);
  wire do_halt = v_d & (op_d == OP_HALT);

  // ------------------------- sequential ------------------------------------
  // control state : has reset
  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      pc     <= 32'd0;
      halted <= 1'b0;
      v_d    <= 1'b0;
    end else if (!halted) begin
      v_d <= 1'b1;
      if (do_halt)      halted <= 1'b1;
      else if (taken)   pc <= {{16{imm_d[15]}}, imm_d};
      else              pc <= pc + 32'd1;
    end
  end

  // datapath state : NO reset  (this is what X-corrupts in GLS)
  // NB: v_w is deliberately not reset -- only the first stage's valid bit is,
  // which is common practice.  In RTL the `if (v_w & we_w)` guard masks the
  // resulting X (X-optimism); in gates the same guard is a mux that lets X
  // through (X-pessimism).  That asymmetry is the divergence under study.
  always @(posedge clk) begin
    v_w     <= v_d;
    ir_d    <= imem_data;
    pc_d    <= pc;
    alu_r_w <= alu_r;
    rd_w    <= rd_d;
    we_w    <= writes_rd;
    pc_w    <= pc_d;
    op_w    <= op_d;
  end

  // register file write : NO reset
  always @(posedge clk) begin
    if (v_w & we_w) rf[rd_w] <= alu_r_w;
  end

  // data memory write : NO reset
  always @(posedge clk) begin
    if (v_d & (op_d == OP_ST)) dmem[opa[2:0]] <= opb;
  end

  assign imem_addr   = pc[5:0];
  assign pc_o        = pc;
  assign halted_o    = halted;
  assign retire_v_o  = v_w;
  assign retire_pc_o = pc_w;
  assign retire_op_o = op_w;
  assign retire_rd_o = rd_w;
  assign retire_val_o= alu_r_w;

endmodule
