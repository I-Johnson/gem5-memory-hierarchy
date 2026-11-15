import argparse
import m5
from m5.objects import *
# gem5 v26: x86 CPUs are X86MinorCPU / X86O3CPU (exported by m5.objects)

p = argparse.ArgumentParser()
p.add_argument('--cpu', choices=['minor', 'o3'], default='minor')
p.add_argument('--width', type=int, default=4)
p.add_argument('--bp', choices=['local', 'bimode', 'tournament', 'ltage'], default='tournament')
p.add_argument('--bin', dest='binary', required=True)
p.add_argument('--bin2', default=None)
p.add_argument('--maxtick', type=int, default=0)
p.add_argument('--outdir', default='m5out')
args = p.parse_args()

system = System()
system.clk_domain = SrcClockDomain(clock='2GHz', voltage_domain=VoltageDomain())
system.mem_mode = 'timing'
system.mem_ranges = [AddrRange('2GB')]
system.membus = SystemXBar()

if args.cpu == 'minor':
    system.cpu = X86MinorCPU()
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
    # gem5 v26: the direction predictor sits inside a BranchPredictor wrapper
    cond = {'local': LocalBP, 'bimode': BiModeBP, 'tournament': TournamentBP, 'ltage': LTAGE}[args.bp]()
    system.cpu.branchPred = BranchPredictor(conditionalBranchPred=cond)
    if args.bin2:
        system.multi_thread = True  # required for numThreads > 1 (base.cc assert)
        system.cpu.numThreads = 2

# Supported helper wires CPU icache/dcache ports to the L1 caches
system.cpu.addPrivateSplitL1Caches(
    Cache(size='32kB', assoc=8, tag_latency=1, data_latency=1,
          response_latency=1, mshrs=8, tgts_per_mshr=16),
    Cache(size='32kB', assoc=8, tag_latency=1, data_latency=1,
          response_latency=1, mshrs=8, tgts_per_mshr=16))
# x86 page-table walker ports (needed once caches sit between CPU and bus)
system.cpu.mmu.connectWalkerPorts(system.membus.cpu_side_ports,
                                  system.membus.cpu_side_ports)
system.cpu.icache.mem_side = system.membus.cpu_side_ports
system.cpu.dcache.mem_side = system.membus.cpu_side_ports

system.mem_ctrl = MemCtrl()
system.mem_ctrl.dram = DDR3_1600_8x8()
system.mem_ctrl.dram.range = system.mem_ranges[0]
system.mem_ctrl.port = system.membus.mem_side_ports
system.system_port = system.membus.cpu_side_ports

system.workload = SEWorkload.init_compatible(args.binary)

proc1 = Process()
proc1.cmd = [args.binary]
proc1.pid = 100
if args.bin2:
    proc2 = Process()
    proc2.cmd = [args.bin2]
    proc2.pid = 101
    system.cpu.workload = [proc1, proc2]
else:
    system.cpu.workload = proc1
system.cpu.createThreads()
system.cpu.createInterruptController()

# x86 SE interrupt wiring
for i in range(system.cpu.numThreads):
    system.cpu.interrupts[i].pio = system.membus.mem_side_ports
    system.cpu.interrupts[i].int_requestor = system.membus.cpu_side_ports
    system.cpu.interrupts[i].int_responder = system.membus.mem_side_ports

root = Root(full_system=False, system=system)
m5.instantiate()
event = m5.simulate(args.maxtick) if args.maxtick else m5.simulate()
print('Exiting @ tick %i because %s' % (m5.curTick(), event.getCause()))
