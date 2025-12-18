# HLS Kernel Details

## Top‑Level Interface

The kernel is implemented as a single top‑level function suitable for Vitis HLS:

```cpp
void monte_carlo_kernel(
    const float *Z,
    float *sum_out,
    int   N,
    float S0,
    float K,
    float T,
    float r,
    float sigma
);
```

* `Z` and `sum_out` are connected through **AXI4‑Master** interfaces so the kernel can read and write directly to DDR.
* All scalar arguments and control signals use **AXI4‑Lite**, allowing the processing system (PS) to configure parameters and start the kernel via registers.

---

## Monte Carlo Computation

For each Monte Carlo path indexed by (i):

1. Read one standard normal random draw:

   $$
   Z_i = Z[i]
   $$

2. Compute the log‑price exponent:

  <p align="center">
  <img src="/img/log_price_exp.png" >
  </p>


3. Compute the terminal asset price:

  <p align="center">
  <img src="/img/terminal_asset_price.png" >
  </p>

4. Compute the European call payoff and accumulate:

  <p align="center">
  <img src="/img/payoff.png" >
  </p>

The kernel accumulates the following into a running sum:

$$
\sum_{i=0}^{N-1} \text{payoff}_i
$$

At the end of the computation, the accumulated payoff is written to `sum_out[0]`. The host code completes the pricing by computing:

$$
\text{Price} = e^{-rT} \cdot \frac{1}{N} \sum_{i=0}^{N-1} \text{payoff}_i
$$

---

## Parallelism and Pipelining

To exploit FPGA parallelism, the kernel evaluates multiple paths per cycle using a fixed number of **lanes** (8, in this case):

* The input array `Z` is accessed so that each lane processes a disjoint subset of paths.
* The main computation loop is **pipelined with initiation interval (II) = 1**, meaning a new group of lanes enters the pipeline every clock cycle once the pipeline is full.
* Each lane maintains its own local accumulator in a small on‑chip array of partial sums.

After all paths have been processed, a short reduction loop sums the lane‑wise partial sums into a single scalar result.
