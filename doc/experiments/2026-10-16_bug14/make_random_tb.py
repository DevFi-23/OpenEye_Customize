"""Module-level random lock-step of psum_pipeline_orig vs psum_pipeline_fix (hardware generics)."""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "psum_pipeline_fix.v")).read()
header = src[src.index("module psum_pipeline_fix"):src.index(");", src.index(") (")) + 2]
ports = [(m.group(1), m.group(2) or "", m.group(3)) for m in re.finditer(
    r"^\s*(input|output)\s+(?:wire|reg)?\s*(\[[^\]]+\])?\s*(\w+)\s*,?\s*$", header, re.M)]
assert len(ports) == 77
G = dict(CLUSTER_ROWS=2, CLUSTER_COLUMNS=2, NUM_GLB_IACT=1, NUM_GLB_PSUM=4, NUM_GLB_WGHT=3, CLUSTERS=4, PARALLEL_MACS=2,
         TRANS_WORDS=8, TRANS_BITWIDTH_PSUM=20, BUFFER_WIDTH=14, DMA_BITWIDTH=64, ROUTER_MODES_PSUM=3, QUANT_AMOUNT=32,
         DATA_PSUM_BITWIDTH=20, PSUM_PER_PE=32, PSUM_CYCLES_ONE_WORD_ALL_CELLS=5, PSUM_OUTPUT_WORDS=2)
plist = ", ".join(f".{k}({v})" for k, v in G.items())
L = ["`timescale 1ns / 1ps", "module tb_random;"]
L += [f"  localparam {k} = {v};" for k, v in G.items()]
L += ["  reg clk_i = 0, rst_n = 0;", "  always #5 clk_i = ~clk_i;"]
for d, w, n in ports:
    if n in ("clk_i", "rst_n"):
        continue
    if d == "input":
        L.append(f"  reg {w} {n};")
    else:
        L.append(f"  wire {w} {n}__fix, {n}__orig;")
for tag in ("fix", "orig"):
    conns = ", ".join(f".{n}({n}{'__' + tag if d == 'output' else ''})" for d, w, n in ports)
    L.append(f"  psum_pipeline_{tag} #({plist}) u_{tag} ({conns});")
# random stimulus
L += ["  integer seed = 14, cyc, mism = 0, k;", "  integer state_cycles [0:15];", "  integer calc_set = 0, calc_go = 0, get_wait = 0, get_count = 0, n_cycles = 300000;",
      "  function [1023:0] rnd_bits(input integer dummy); integer i; begin for (i = 0; i < 32; i = i + 1) rnd_bits[i*32+:32] = $random(seed); end endfunction",
      "  task randomize_inputs; begin"]
for d, w, n in ports:
    if d != "input" or n in ("clk_i", "rst_n"):
        continue
    if n in ("psum_ready_o_reg", "psum_enable_o"):
        # mostly all ones so that the 8-term AND is often true, sometimes a few zeros
        L.append(f"    {n} = (($random(seed) & 3) != 0) ? ~0 : (rnd_bits(0) | rnd_bits(0));")
    elif n in ("wght_enable_i_reg", "iact_enable_i_oep_w"):
        L.append(f"    {n} = (($random(seed) & 15) == 0) ? rnd_bits(0) : 0;")
    elif n == "compute_reg":
        L.append(f"    {n} = (($random(seed) & 31) == 0);")
    elif n == "status_reg_enable_reg":
        L.append(f"    {n} = (($random(seed) & 1023) == 0);")
    elif n in ("filters", "trans_cycles_psum", "needed_cycles", "output_words", "fsm_psum_limit"):
        L.append(f"    {n} = $random(seed) & 15;")
    elif n == "fsm_current_state":
        L.append(f"    {n} = (($random(seed) & 7) == 0) ? 4'd5 : $random(seed);")
    elif n in ("enable_dma_i_reg", "ready_dma_i", "send_data_out"):
        L.append(f"    {n} = (($random(seed) & 3) != 0);")
    else:
        L.append(f"    {n} = rnd_bits(0);")
L += ["  end endtask", "  initial begin",
      "    for (k = 0; k < 16; k = k + 1) state_cycles[k] = 0;",
      "    randomize_inputs; #23 rst_n = 1;",
      "    for (cyc = 0; cyc < n_cycles; cyc = cyc + 1) begin",
      "      @(negedge clk_i);"]
outs = [n for d, w, n in ports if d == "output"]
for n in outs:
    L.append(f"      if ({n}__fix !== {n}__orig) begin mism = mism + 1; if (mism <= 5) $display(\"MISMATCH cycle %0d {n}: fix=%h orig=%h\", cyc, {n}__fix, {n}__orig); end")
L += ["      state_cycles[fsm_psum_current_state__orig] = state_cycles[fsm_psum_current_state__orig] + 1;",
      "      if (fsm_psum_current_state__orig == 2 && u_fix.results_ready_calc && !u_fix.results_ready) calc_set = calc_set + 1;",
      "      if (fsm_psum_current_state__orig == 2 && u_fix.results_ready_calc && u_fix.psum_ready_i_reg != 0) calc_go = calc_go + 1;",
      "      if (fsm_psum_current_state__orig == 3 && !u_fix.all_psum_enable) get_wait = get_wait + 1;",
      "      if (fsm_psum_current_state__orig == 3 && u_fix.all_psum_enable) get_count = get_count + 1;",
      "      if (cyc % 50000 == 0) $display(\"  ... %0d cycles, mismatches %0d\", cyc, mism);",
      "      randomize_inputs;",
      "      if (($random(seed) & 8191) == 0) begin rst_n = 0; @(negedge clk_i); rst_n = 1; end",
      "    end",
      f"    $display(\"random lock-step: %0d cycles, {len(outs)} outputs compared, mismatches = %0d\", cyc, mism);",
      "    $display(\"psum FSM cycles per state: IDLE %0d, WAIT_TO_SEND %0d, CALCULATE %0d, GET_RESULTS %0d, WAIT_FOR_SENDING %0d, SEND_RESULTS %0d, SEND_TO_IACT %0d\","
      " state_cycles[0], state_cycles[1], state_cycles[2], state_cycles[3], state_cycles[4], state_cycles[5], state_cycles[6]);",
      "    $display(\"CALCULATE_PSUM: flag set %0d times, round started (results_ready_calc & ready) in %0d cycles; PSUM_GET_RESULTS: %0d cycles waiting (all_psum_enable=0), %0d cycles counted\", calc_set, calc_go, get_wait, get_count);",
      "    $finish;", "  end", "endmodule", ""]
open(os.path.join(HERE, "tb_random.v"), "w").write("\n".join(L))
print("written tb_random.v")
