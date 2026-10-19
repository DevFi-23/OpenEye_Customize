# Bug #14 fix verification: psum_pipeline (fixed RTL) out of context with the fix67 hardware generics.
set here [file normalize [file dirname [info script]]]
read_verilog -sv [file join $here .. fix14_impl rtl psum_pipeline.v]
read_verilog -sv [file join $here .. fix14_impl rtl quantization_unit.v]
synth_design -top psum_pipeline -part xczu7ev-ffvc1156-2-e -mode out_of_context -flatten_hierarchy rebuilt -generic {
    CLUSTER_ROWS=2 CLUSTER_COLUMNS=2 NUM_GLB_IACT=1 NUM_GLB_PSUM=4 NUM_GLB_WGHT=3 CLUSTERS=4
    PARALLEL_MACS=2 TRANS_WORDS=8 TRANS_BITWIDTH_PSUM=20 BUFFER_WIDTH=14 DMA_BITWIDTH=64
    ROUTER_MODES_PSUM=3 QUANT_AMOUNT=32 DATA_PSUM_BITWIDTH=20 PSUM_PER_PE=32
    PSUM_CYCLES_ONE_WORD_ALL_CELLS=5 PSUM_OUTPUT_WORDS=2}
report_utilization -file [file join $here synth_fix14_util.txt]
write_verilog -force -mode funcsim [file join $here psum_pipeline_fix14_ooc_funcsim.v]
