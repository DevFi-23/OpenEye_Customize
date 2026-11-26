# timing_requant.tcl: static timing of the requantization / activation path on the routed checkpoint of the hardware
# baseline 2026-11-22 (fix51, xczu7ev-ffvc1156-2-e, 4 ns). Run in batch from the checkpoint folder:
#   vivado.bat -mode batch -nojournal -nolog -source timing_requant.tcl
# Writes timing_requant.rpt next to it. Read-only: opens the checkpoint, reports, exits.
open_checkpoint reports/OpenEye_FPGA_route.dcp
set out [open timing_requant.rpt w]
proc section {out title} { puts $out "\n######## $title" }
proc cells {pattern} { return [get_cells -hier -quiet -filter "NAME =~ $pattern"] }

section $out "clock"
puts $out [report_clocks -return_string]

# cell names that exist (a few), to see what synthesis kept of the quantizer and the table
foreach p {"*gen_quant_unit[0]*u_quant_unit*" "*gen_quant_unit[0]*u_act_table*" "*iact_to_psum_mux_reg[7]*"} {
  set c [cells $p]
  section $out "cells $p: [llength $c]"
  foreach x [lrange $c 0 40] { puts $out "  $x  ([get_property REF_NAME $x])" }
}

set qu   [cells "*gen_quant_unit[*]*u_quant_unit*"]
set tab  [cells "*gen_act_table*u_act_table*"]
set r5   [cells "*iact_to_psum_mux_reg*"]

section $out "R4 -> table -> mux -> R5: worst paths through the activation tables"
puts $out [report_timing -through $tab -to $r5 -max_paths 8 -nworst 1 -delay_type max -return_string]
section $out "R4 -> R5 without the table (modes 0/1 path), worst paths"
puts $out [report_timing -from $qu -to $r5 -max_paths 4 -nworst 1 -delay_type max -return_string]
section $out "inside the quantizer (stage 1 -> 2 -> 3): worst register-to-register paths"
puts $out [report_timing -from $qu -to $qu -max_paths 12 -nworst 1 -delay_type max -return_string]
section $out "into the quantizer (psum buffer / control -> stage 1 registers)"
puts $out [report_timing -to $qu -max_paths 6 -nworst 1 -delay_type max -return_string]
section $out "table write path (DMA register -> LUTRAM write)"
puts $out [report_timing -to $tab -max_paths 4 -nworst 1 -delay_type max -return_string]
section $out "design WNS"
puts $out [report_timing -max_paths 1 -return_string]
close $out
exit
