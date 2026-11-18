// Area estimate only (Yosys), not part of the RTL: the weight-row assembly of GET_WGHT in OpenEye_FPGA.v at the
// baseline configuration (4 clusters x NUM_GLB_WGHT 3 x PARALLEL_MACS 2 = 24 weights per row, 12 bits each in a
// sparse build = 288 bits, DMA 64), as today (RAW_EN = 0: 5 DMA words shifted in, row written) and with the per-layer
// raw weight format of P1 (RAW_EN = 1: when raw_i, 3 DMA words of 8-bit weights, each expanded to a 12-bit field with
// overhead 0 when the row is written). Field layout assumed {overhead[3:0], value[7:0]}.
module p1_wght_row #(
    parameter RAW_EN = 1,
    parameter DMA = 64,
    parameter WEIGHTS = 24
) (
    input  wire                 clk_i,
    input  wire                 rst_n,
    input  wire                 en_i,
    input  wire                 raw_i,
    input  wire [DMA-1:0]       data_i,
    output reg                  we_o,
    output reg  [WEIGHTS*12-1:0] row_o
);
  localparam WORDS_CSC = (WEIGHTS * 12 + DMA - 1) / DMA;   // 5
  localparam WORDS_RAW = (WEIGHTS * 8 + DMA - 1) / DMA;    // 3
  reg [WORDS_CSC*DMA-1:0] shift;
  reg [2:0] count;
  wire last = (RAW_EN == 1 && raw_i) ? (count == WORDS_RAW - 1) : (count == WORDS_CSC - 1);
  wire [WORDS_CSC*DMA-1:0] next = {shift[(WORDS_CSC-1)*DMA-1:0], data_i};
  integer w;
  always @(posedge clk_i or negedge rst_n) begin
    if (!rst_n) begin
      shift <= 0; count <= 0; we_o <= 0; row_o <= 0;
    end else begin
      we_o <= 0;
      if (en_i) begin
        shift <= next;
        count <= last ? 3'd0 : count + 3'd1;
        if (last) begin
          we_o <= 1;
          if (RAW_EN == 1 && raw_i) begin
            for (w = 0; w < WEIGHTS; w = w + 1)
              row_o[w*12+:12] <= {4'd0, next[w*8+:8]};
          end else begin
            row_o <= next[WEIGHTS*12-1:0];
          end
        end
      end
    end
  end
endmodule
