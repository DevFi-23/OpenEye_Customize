# Bug #14 analysis (read only): what did synthesis build for psum_pipeline.results_ready?
set here [file normalize [file dirname [info script]]]
open_checkpoint [file join $here .. fix67_impl reports OpenEye_FPGA_synth.dcp]
set f [open [file join $here inspect.txt] w]
set rr [get_cells -hier -filter {NAME =~ *psum_pipeline_inst/results_ready*}]
puts $f "results_ready cells: $rr"
foreach c $rr {
    puts $f "  $c REF=[get_property REF_NAME $c] INIT=[get_property -quiet INIT $c]"
    foreach p [get_pins -of $c] {
        set n [get_nets -quiet -of $p]
        puts $f "    pin [get_property REF_PIN_NAME $p] dir=[get_property DIRECTION $p] net=$n"
    }
    set fi [all_fanin -flat -startpoints_only [get_pins $c/D]]
    puts $f "  D fan-in startpoints ([llength $fi]):"
    foreach s [lsort $fi] { puts $f "    $s" }
    set fo [all_fanout -flat -endpoints_only [get_pins $c/Q]]
    puts $f "  Q fan-out endpoints ([llength $fo]):"
    foreach s [lsort [lrange $fo 0 60]] { puts $f "    $s" }
}
set pp [get_cells -quiet psum_pipeline_inst]
puts $f "psum_pipeline_inst: $pp IS_PRIMITIVE=[get_property -quiet IS_PRIMITIVE $pp] pins=[llength [get_pins -quiet -of $pp]]"
close $f
write_verilog -force -mode funcsim -cell psum_pipeline_inst [file join $here psum_pipeline_inst_synth_funcsim.v]
