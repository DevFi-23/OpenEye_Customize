// Bug #19 verification (not project RTL): the old and new CONVERT_IACT store condition differ only when
// fully_connected_layer = 1 and current_x < 0 in state CONVERT_IACT. Extra root module (-s fc_guard_monitor).
module fc_guard_monitor;
  integer fc_cycles = 0;
  integer fc_negative_x = 0;
  integer fc_negative_x_convert = 0;
  always @(posedge OpenEye_FPGA.clk_i) begin
    if (OpenEye_FPGA.fully_connected_layer === 1'b1) begin
      fc_cycles = fc_cycles + 1;
      if (OpenEye_FPGA.current_x < 0) begin
        fc_negative_x = fc_negative_x + 1;
        if (OpenEye_FPGA.fsm_current_state == OpenEye_FPGA.CONVERT_IACT) fc_negative_x_convert = fc_negative_x_convert + 1;
        $display("FC GUARD EVENT t=%0t state=%0d current_x=%0d fully_connected_layer=%b", $time, OpenEye_FPGA.fsm_current_state,
                 OpenEye_FPGA.current_x, OpenEye_FPGA.fully_connected_layer);
      end
    end
  end
  final $display("FC GUARD: %0d FC cycles, %0d with current_x < 0, %0d of them in CONVERT_IACT", fc_cycles, fc_negative_x, fc_negative_x_convert);
endmodule
