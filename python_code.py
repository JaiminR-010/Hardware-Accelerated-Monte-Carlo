import time
import ctypes
import numpy as np
from pynq import Overlay, allocate
import math

# Monte Carlo parameters
N     = 1000        # larger N give better approximations
S0    = 100.0       # initial stock price
K     = 105.0       # strike price for the option
T     = 1.0         # time to maturity in years
r     = 0.05        # risk-free interest rate (annual)
sigma = 0.2         # volatility (also annual)

# common Z value for both CPU and FPGA calculations
np.random.seed(42)
Z = np.random.standard_normal(N).astype(np.float32)

# CPU Monte Carlo
def cpu_monte_carlo(Z, S0, K, T, r, sigma):
    drift  = (r - 0.5 * sigma * sigma) * T
    vol_dt = sigma * math.sqrt(T)
    payoff_sum = 0.0
    # loop calculates the simulated stock price for each random Z generated above
    for z in Z:
        ST = S0 * math.exp(drift + vol_dt * z)
        payoff = max(ST - K, 0.0) # payoff formula for European options
        payoff_sum += payoff
    return payoff_sum

# time calculation for CPU begins
t0 = time.time()
cpu_sum = cpu_monte_carlo(Z, S0, K, T, r, sigma)
t_cpu = time.time() - t0
# time calculation for CPU ends

# discounting to present value 
cpu_price = math.exp(-r * T) * cpu_sum / N

# print results for CPU
print(f"CPU payoff sum: ${cpu_sum:.2f}")
print(f"CPU option price: ${cpu_price:.2f}")
print(f"CPU time: {t_cpu*1000:.2f} ms")
print()

# FPGA Monte Carlo
overlay = Overlay("design_1.bit")
ip = overlay.monte_carlo_kernel_0

# dynamic memory allocation for Z and sum_out
Z_buf = allocate(shape=(N,), dtype=np.float32)
out_buf = allocate(shape=(1,), dtype=np.float32)

Z_buf[:] = Z

# function to covnert floats into int
def float_to_uint32(f):
    return ctypes.c_uint32(np.frombuffer(np.float32(f).tobytes(), dtype=np.uint32)[0]).value

# store the physical address because m_axi expects it
Z_addr = Z_buf.device_address
out_addr = out_buf.device_address

# 64-bit addresses -> split into 2 32-bit addresses
ip.register_map.Z_1 = Z_addr & 0xFFFFFFFF
ip.register_map.Z_2 = (Z_addr >> 32) & 0xFFFFFFFF
ip.register_map.sum_out_1 = out_addr & 0xFFFFFFFF
ip.register_map.sum_out_2 = (out_addr >> 32) & 0xFFFFFFFF

# PYNQ accepts int easily, floats require extra hassle
ip.register_map.N = N
ip.register_map.S0 = float_to_uint32(S0)
ip.register_map.K = float_to_uint32(K)
ip.register_map.T = float_to_uint32(T)
ip.register_map.r = float_to_uint32(r)
ip.register_map.sigma = float_to_uint32(sigma)

# time calculation for FPGA begins
# IMPORTANT - it only times the kernel execution and not the data transfer
t0 = time.time()
ip.register_map.CTRL.AP_START = 1        # start the kernel
while ip.register_map.CTRL.AP_DONE == 0: # wait unitl it finishes running
    pass
t_fpga = time.time() - t0
# time calculation for FPGA ends

# update CPU cache
out_buf.invalidate()
fpga_sum = float(out_buf[0])    # back to float 
fpga_price = math.exp(-r * T) * fpga_sum / N        # discounting the sum and dividing by N

# print results for FPGA
print(f"FPGA payoff sum: ${fpga_sum:.2f}")
print(f"FPGA option price: ${fpga_price:.2f}")
print(f"FPGA kernel time: {t_fpga*1000:.2f} ms")