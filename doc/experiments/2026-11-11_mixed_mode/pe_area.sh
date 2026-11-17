#!/bin/bash
# pe_area.sh [yosys]: Yosys estimate of one PE (hdl/PE.v and its submodules, PARALLEL_MACS 2) built sparse
# (SPARSITY_EN 1) and dense (SPARSITY_EN 0), cells per module (synth_xilinx, not flattened), for the mixed-mode
# proposal of README_FI section 2 ("Chế độ trộn"). A rough split of the weight-side logic, not Vivado numbers.
# From the repository root; logs in /tmp/pe_area_<sparsity>.log.
Y=${1:-$HOME/tools/yosys/bin/yosys}
F="hdl/PE.v hdl/SPad_DP.v hdl/SPad_DP_RW.v hdl/SPad_SP.v hdl/adder.v hdl/adder_tree.v hdl/data_pipeline_iact.v
   hdl/data_pipeline_wght.v hdl/dsp_unit.v hdl/multiplier.v hdl/mux_iact.v hdl/mux2.v hdl/demux2.v hdl/RAM_DP.v
   hdl/RAM_DP_RW.v hdl/RAM_DP_RW_generic.v hdl/RAM_DP_generic.v hdl/RAM_SP.v hdl/RAM_SP_generic.v"
for sp in 1 0; do
  inc=$(mktemp -d)
  printf "parameter PARALLEL_MACS = 2,\nparameter SPARSITY_EN = %s,\n" "$sp" > "$inc/parameters_PE.vh"
  "$Y" -q -l /tmp/pe_area_$sp.log -p "read_verilog -sv -DNO_TRACE -DSYNTHESIS -I$inc -Ihdl/include $(echo $F);
                                       synth_xilinx -top PE; stat" > /dev/null
  echo "== SPARSITY_EN=$sp: LUTs per module (data_pipeline_wght / data_pipeline_iact / PE itself), LUTRAM cells"
  # only the last "Printing statistics" block (synth_xilinx prints one as well); module = first name after "\\"
  awk '/Printing statistics/{n++} {line[NR]=$0; blk[NR]=n} END{
         for(i=1;i<=NR;i++){ if(blk[i]!=n) continue; $0=line[i]
           if($1=="==="){m=$2; split(m,a,"\\"); mod=(length(a)>1)?a[2]:m; if(m=="design") mod=""}
           else if(mod!="" && $2 ~ /^LUT[1-6]$/) l[mod]+=$1
           else if(mod!="" && $2 ~ /^RAM(32|64|128)/) r[mod " " $2]+=$1 }
         for(k in l) printf "  %-22s %5d LUT (one instance)\n", k, l[k]
         for(k in r) printf "  %-34s %3d\n", k, r[k]}' /tmp/pe_area_$sp.log
  rm -rf "$inc"
done
