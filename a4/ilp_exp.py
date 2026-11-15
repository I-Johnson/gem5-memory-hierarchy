# MSCS-531 Assignment 4 Part 2 - gem5 v26 SE-mode configuration (x86)
#
#   --cpu minor            in-order pipelined core: Fetch1 -> Fetch2 -> Decode
#                          -> Execute (memory access + writeback/commit inside
#                          Execute). Single-issue (all widths = 1).
#   --cpu o3 --width N     out-of-order superscalar; fetch/decode/rename/
#                          dispatch/issue/writeback/commit widths all = N
#   --bp none|local|bimode|tournament|ltage
#                          'none' = static predict-not-taken for every
#                          conditional branch (no learning). Note: on x86,
#                          MinorCPU makes no predictor lookups at all, so
#                          branch-predictor experiments use O3.
#   --bin2 PROG            second hardware thread on the same O3 core (SMT)
#   --maxtick T            stop after T ticks (0 = run to completion)
import argparse

import m5
from m5.objects import *

p = argparse.ArgumentParser()
p.add_argument("--cpu", choices=["minor", "o3"], default="minor")
p.add_argument("--width", type=int, default=4)
p.add_argument(
    "--bp",
    choices=["none", "local", "bimode", "tournament", "ltage"],
    default="tournament",
)
p.add_argument("--bin", dest="binary", required=True)
p.add_argument("--bin2", default=None)
p.add_argument("--maxtick", type=int, default=0)
args = p.parse_args()


def make_bp(kind):
    cond = {
        # StaticNotTakenBP is added to gem5 for this assignment
        # (src/cpu/pred/static_nt.hh): every conditional branch is
        # predicted not taken and nothing is learned.
        "none": StaticNotTakenBP,
        "local": LocalBP,
        "bimode": BiModeBP,
        "tournament": TournamentBP,
        "ltage": LTAGE,
    }[kind]()
    return BranchPredictor(conditionalBranchPred=cond)


system = System()
system.clk_domain = SrcClockDomain(
    clock="2GHz", voltage_domain=VoltageDomain()
)
system.mem_mode = "timing"
system.mem_ranges = [AddrRange("2GiB")]
system.membus = SystemXBar()

if args.cpu == "minor":
    # gem5 v26 exports ISA-specific CPU classes
    system.cpu = X86MinorCPU()
    system.cpu.branchPred = make_bp(args.bp)
else:
    system.cpu = X86O3CPU()
    w = args.width
    system.cpu.fetchWidth = w
    system.cpu.decodeWidth = w
    system.cpu.renameWidth = w
    system.cpu.dispatchWidth = w
    system.cpu.issueWidth = w
    system.cpu.wbWidth = w
    system.cpu.commitWidth = w
    system.cpu.squashWidth = w
    # width-1 O3 panics with TimeBuffer out-of-bounds at the default
    # size 5; these only size the inter-stage buffers, not timing.
    system.cpu.forwardComSize = 10
    system.cpu.backComSize = 10
    system.cpu.branchPred = make_bp(args.bp)
    if args.bin2:
        system.multi_thread = True  # required when numThreads > 1
        system.cpu.numThreads = 2

system.cpu.addPrivateSplitL1Caches(
    Cache(size="32KiB", assoc=8, tag_latency=1, data_latency=1,
          response_latency=1, mshrs=8, tgts_per_mshr=16),
    Cache(size="32KiB", assoc=8, tag_latency=1, data_latency=1,
          response_latency=1, mshrs=8, tgts_per_mshr=16),
)
system.cpu.mmu.connectWalkerPorts(
    system.membus.cpu_side_ports, system.membus.cpu_side_ports
)
system.cpu.icache.mem_side = system.membus.cpu_side_ports
system.cpu.dcache.mem_side = system.membus.cpu_side_ports

system.mem_ctrl = MemCtrl()
system.mem_ctrl.dram = DDR3_1600_8x8()
system.mem_ctrl.dram.range = system.mem_ranges[0]
system.mem_ctrl.port = system.membus.mem_side_ports
system.system_port = system.membus.cpu_side_ports

system.workload = SEWorkload.init_compatible(args.binary)

proc1 = Process(pid=100, cmd=[args.binary])
if args.bin2:
    proc2 = Process(pid=101, cmd=[args.bin2])
    system.cpu.workload = [proc1, proc2]
else:
    system.cpu.workload = proc1
system.cpu.createThreads()
system.cpu.createInterruptController()

for i in range(system.cpu.numThreads):
    system.cpu.interrupts[i].pio = system.membus.mem_side_ports
    system.cpu.interrupts[i].int_requestor = system.membus.cpu_side_ports
    system.cpu.interrupts[i].int_responder = system.membus.mem_side_ports

root = Root(full_system=False, system=system)
m5.instantiate()
event = m5.simulate(args.maxtick) if args.maxtick else m5.simulate()
print(f"Exiting @ tick {m5.curTick()} because {event.getCause()}")
