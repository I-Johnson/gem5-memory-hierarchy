# MSCS-531 Assignment 3 - gem5 cache + TLB experiment configuration
# Based on gem5 v26 configs/learning_gem5/part1/two_level.py, extended with
# CLI options for cache size, associativity, cache line size, and TLB size.
import argparse
import os

import m5
from m5.objects import *

parser = argparse.ArgumentParser()
parser.add_argument("--binary", required=True)
parser.add_argument("--l1i_size", default="16KiB")
parser.add_argument("--l1d_size", default="64KiB")
parser.add_argument("--l2_size", default="256KiB")
parser.add_argument("--l1i_assoc", type=int, default=2)
parser.add_argument("--l1d_assoc", type=int, default=2)
parser.add_argument("--l2_assoc", type=int, default=8)
parser.add_argument("--cacheline_size", type=int, default=64)
parser.add_argument("--itb_size", type=int, default=64)
parser.add_argument("--dtb_size", type=int, default=64)
parser.add_argument("--mem_size", default="1GiB")
args, prog_args = parser.parse_known_args()
for a in prog_args:
    if a.startswith("--"):
        raise SystemExit(f"error: unknown flag {a}")
# prog_args are passed to the benchmark as its argv[1:]


class L1Cache(Cache):
    tag_latency = 2
    data_latency = 2
    response_latency = 2
    mshrs = 4
    tgts_per_mshr = 20

    def connectBus(self, bus):
        self.mem_side = bus.cpu_side_ports


class L1ICache(L1Cache):
    def __init__(self, opts):
        super().__init__()
        self.size = opts.l1i_size
        self.assoc = opts.l1i_assoc

    def connectCPU(self, cpu):
        self.cpu_side = cpu.icache_port


class L1DCache(L1Cache):
    def __init__(self, opts):
        super().__init__()
        self.size = opts.l1d_size
        self.assoc = opts.l1d_assoc

    def connectCPU(self, cpu):
        self.cpu_side = cpu.dcache_port


class L2Cache(Cache):
    tag_latency = 20
    data_latency = 20
    response_latency = 20
    mshrs = 20
    tgts_per_mshr = 12

    def __init__(self, opts):
        super().__init__()
        self.size = opts.l2_size
        self.assoc = opts.l2_assoc

    def connectCPUSideBus(self, bus):
        self.cpu_side = bus.mem_side_ports

    def connectMemSideBus(self, bus):
        self.mem_side = bus.cpu_side_ports


system = System()
system.clk_domain = SrcClockDomain()
system.clk_domain.clock = "1GHz"
system.clk_domain.voltage_domain = VoltageDomain()
system.mem_mode = "timing"
system.mem_ranges = [AddrRange(args.mem_size)]
system.cache_line_size = args.cacheline_size

system.cpu = X86TimingSimpleCPU()

# TLB sizes (X86MMU itb/dtb are X86TLB with a 'size' param, default 64)
system.cpu.mmu.itb.size = args.itb_size
system.cpu.mmu.dtb.size = args.dtb_size

system.cpu.icache = L1ICache(args)
system.cpu.dcache = L1DCache(args)
system.cpu.icache.connectCPU(system.cpu)
system.cpu.dcache.connectCPU(system.cpu)

system.l2bus = L2XBar()
system.cpu.icache.connectBus(system.l2bus)
system.cpu.dcache.connectBus(system.l2bus)

system.l2cache = L2Cache(args)
system.l2cache.connectCPUSideBus(system.l2bus)

system.membus = SystemXBar()
system.l2cache.connectMemSideBus(system.membus)

system.cpu.createInterruptController()
system.cpu.interrupts[0].pio = system.membus.mem_side_ports
system.cpu.interrupts[0].int_requestor = system.membus.cpu_side_ports
system.cpu.interrupts[0].int_responder = system.membus.mem_side_ports

system.system_port = system.membus.cpu_side_ports

system.mem_ctrl = MemCtrl()
system.mem_ctrl.dram = DDR3_1600_8x8()
system.mem_ctrl.dram.range = system.mem_ranges[0]
system.mem_ctrl.port = system.membus.mem_side_ports

system.workload = SEWorkload.init_compatible(args.binary)

process = Process()
process.cmd = [args.binary] + prog_args
system.cpu.workload = process
system.cpu.createThreads()

root = Root(full_system=False, system=system)
m5.instantiate()
print("Beginning simulation!")
exit_event = m5.simulate()
print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")
