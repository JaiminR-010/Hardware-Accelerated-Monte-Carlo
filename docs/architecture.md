# Architecture & Design

## Overview

This project accelerates a Monte Carlo simulation for European option pricing by offloading the payoff computation to an FPGA, while keeping control logic and post‑processing on the CPU (ARM core on the PYNQ board). The same standard normal samples are used for both CPU and FPGA runs to allow a fair comparison of price and runtime.

## System Components

- **CPU side (Python/NumPy)**  
  - Generates \(N\) standard normal random variables.  
  - Runs a baseline Monte Carlo implementation on the CPU.  
  - Sets up buffers and registers for the FPGA kernel, launches it, and reads back results.

- **FPGA kernel (Vitis HLS C/C++)**  
  - Receives an array of normals \(Z\) and scalar parameters.  
  - Computes terminal prices and payoffs in parallel lanes.  
  - Outputs a single sum of all path payoffs to external memory.

- **Zynq SoC / PYNQ‑Z2 board**  
  - ARM cores run the Python host code.  
  - Programmable logic region hosts the Monte Carlo kernel as a custom IP block.  
  - AXI interconnect links the PS, kernel, and DDR memory.

## Data Flow

1. Python allocates two buffers in DDR: one for the \(Z\) array, one for the payoff sum.  
2. The bitstream is loaded; PYNQ exposes the HLS IP as a Python object with a register map.  
3. Python writes buffer addresses and scalar parameters into the kernel’s control registers and starts the kernel.  
4. The kernel streams \(Z[i]\) values from DDR, computes payoffs in parallel, and writes the final sum to the output buffer.  
5. Python invalidates the output buffer cache, reads the sum, divides by \(N\), applies the discount factor, and compares price and runtime to the CPU baseline.

## Design Goals

- Achieve large speedups versus a single‑threaded CPU implementation for large \(N\).  
- Keep numerical error within typical Monte Carlo sampling error.  
- Maintain a clean separation between hardware (kernel) and software (Python host) so experiments are easy to reproduce and extend.
