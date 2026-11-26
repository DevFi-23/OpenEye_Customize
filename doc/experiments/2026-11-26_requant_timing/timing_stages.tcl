# timing_stages.tcl: worst setup path INTO each register stage of the quantizer and into the write-back register, on the
# routed checkpoint of 2026-11-22 (fix51). Writes timing_stages.rpt. Read-only.
open_checkpoint reports/OpenEye_FPGA_route.dcp
set out [open timing_stages.rpt w]
proc cells {pattern} { return [get_cells -hier -quiet -filter "NAME =~ $pattern"] }
foreach {title pattern} {
  "S1: sum_s1 / mant_s1 / shift_s1 / round_s1 (psum + offset, choice of [mant, shift])" "*u_quant_unit/*_s1_reg*"
  "S2: prod_s2 (mant x sum + rounding constant)"                                        "*u_quant_unit/prod_s2_reg*"
  "S2: shift_s2"                                                                        "*u_quant_unit/shift_s2_reg*"
  "S3 = R4: quantized_value (shift, clamp)"                                             "*u_quant_unit/quantized_value_reg*"
  "R5: iact_to_psum_mux_reg (table, mux)"                                               "*iact_to_psum_mux_reg*"
} {
  set c [cells $pattern]
  puts $out "\n######## $title: [llength $c] cells"
  if {[llength $c] > 0} { puts $out [report_timing -to $c -max_paths 1 -nworst 1 -delay_type max -return_string] }
}
close $out
exit
