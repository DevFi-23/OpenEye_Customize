# Bug #14 analysis (no RTL change): synthesize the results_ready pattern and psum_pipeline
# with the generics of the fix67 hardware, and write functional-simulation netlists.
set here [file normalize [file dirname [info script]]]
set part xczu7ev-ffvc1156-2-e

read_verilog -sv [file join $here mix_test.v]
synth_design -top mix_test -part $part -mode out_of_context
write_verilog -force -mode funcsim [file join $here mix_test_funcsim.v]
close_project

read_verilog -sv [file join $here .. fix67_impl rtl psum_pipeline.v]
read_verilog -sv [file join $here .. fix67_impl rtl quantization_unit.v]
synth_design -top psum_pipeline -part $part -mode out_of_context -flatten_hierarchy rebuilt -generic {
    CLUSTER_ROWS=2 CLUSTER_COLUMNS=2 NUM_GLB_IACT=1 NUM_GLB_PSUM=4 NUM_GLB_WGHT=3 CLUSTERS=4
    PARALLEL_MACS=2 TRANS_WORDS=8 TRANS_BITWIDTH_PSUM=20 BUFFER_WIDTH=14 DMA_BITWIDTH=64
    ROUTER_MODES_PSUM=3 QUANT_AMOUNT=32 DATA_PSUM_BITWIDTH=20 PSUM_PER_PE=32
    PSUM_CYCLES_ONE_WORD_ALL_CELLS=5 PSUM_OUTPUT_WORDS=2}
set f [open [file join $here synth_check.txt] w]
foreach c [lsort [get_cells -hier -filter {NAME =~ *results_ready*}]] {
    puts $f "$c REF=[get_property REF_NAME $c] INIT=[get_property -quiet INIT $c]"
}
close $f
write_verilog -force -mode funcsim [file join $here psum_pipeline_ooc_funcsim.v]
