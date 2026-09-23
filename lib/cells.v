// Simulation models for mocklib.  Deliberately plain: X propagates through
// these cells exactly as a real vendor library would propagate it, so the
// experiment reproduces genuine gate-level X pessimism.
`timescale 1ns/1ps

module INVX1  (input A, output Y);            assign Y = ~A;        endmodule
module BUFX1  (input A, output Y);            assign Y =  A;        endmodule
module NAND2X1(input A, B, output Y);         assign Y = ~(A & B);  endmodule
module NOR2X1 (input A, B, output Y);         assign Y = ~(A | B);  endmodule
module AND2X1 (input A, B, output Y);         assign Y =  (A & B);  endmodule
module OR2X1  (input A, B, output Y);         assign Y =  (A | B);  endmodule
module XOR2X1 (input A, B, output Y);         assign Y =  (A ^ B);  endmodule
module XNOR2X1(input A, B, output Y);         assign Y = ~(A ^ B);  endmodule
module MUX2X1 (input A, B, S, output Y);      assign Y = S ? B : A; endmodule
module AOI21X1(input A, B, C, output Y);      assign Y = ~((A & B) | C); endmodule
module OAI21X1(input A, B, C, output Y);      assign Y = ~((A | B) & C); endmodule

// Non-resettable flop.  Q powers up as 1'bx -- the X-corruption source.
module DFFX1 (input CK, input D, output reg Q);
  always @(posedge CK) Q <= D;
endmodule

// Async active-low reset flop.
module DFFRX1 (input CK, input RN, input D, output reg Q);
  always @(posedge CK or negedge RN)
    if (!RN) Q <= 1'b0;
    else     Q <= D;
endmodule
