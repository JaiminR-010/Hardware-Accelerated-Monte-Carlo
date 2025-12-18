#include <hls_math.h>
#include <stdint.h>

#define LANES 8   // parallel Monte Carlo paths per cycle 

// monte_carlo_kernel is the function that will be turned into the hardware block of the FPGA
void monte_carlo_kernel(
    const float *Z,     // pointer to an array of standard normal random variables
    float *sum_out,     // pointer to the accumulated payoff sum - final putput from the hardware part of the FPGA
    int   N,            // number of simulations - set by the user
    float S0,           // initial stock price
    float K,            // strike price of the option
    float T,            // time period (in years)
    float r,            // risk-free interest rate
    float sigma         // volatility 
) {

// Z and sum_out points to large amounts of data -> AXI Master 
#pragma HLS INTERFACE m_axi    port=Z       offset=slave bundle=gmem
#pragma HLS INTERFACE m_axi    port=sum_out offset=slave bundle=gmem

// rest of the parameters are small, control information -> AXI-Lite
#pragma HLS INTERFACE s_axilite port=Z       bundle=control  // AXI-Lite for Z and sum_out to pass the base address to the hardware 
#pragma HLS INTERFACE s_axilite port=sum_out bundle=control  // base address not hard-coded because memory allocation is dynamic-allocate()
#pragma HLS INTERFACE s_axilite port=N       bundle=control
#pragma HLS INTERFACE s_axilite port=S0      bundle=control
#pragma HLS INTERFACE s_axilite port=K       bundle=control
#pragma HLS INTERFACE s_axilite port=T       bundle=control
#pragma HLS INTERFACE s_axilite port=r       bundle=control
#pragma HLS INTERFACE s_axilite port=sigma   bundle=control
#pragma HLS INTERFACE s_axilite port=return  bundle=control

    // each of the 8 lanes have their own separate storage of its respective sums which are then added together at the end 
    float partial_sum[LANES];
#pragma HLS ARRAY_PARTITION variable=partial_sum complete

    // initialize accumulators
    for (int l = 0; l < LANES; l++) {
#pragma HLS UNROLL
        partial_sum[l] = 0.0f;
    }

    // pre-calculating drift and voltality to avoid calculating it repeatedly in the main loop
    float drift  = (r - 0.5f * sigma * sigma) * T;
    float vol_dt = sigma * hls::sqrtf(T);


main_loop:
    for (int i = 0; i < N; i += LANES) {
#pragma HLS PIPELINE II=1   // creating pipelines so it keeps accepting a new value each clock cycle (maxing throughput)

        for (int l = 0; l < LANES; l++) {
#pragma HLS UNROLL    // run all iterations in parallel
            int idx = i + l;
            if (idx < N) {
                float z = Z[idx];
                float x = drift + vol_dt * z;
                float ST = S0 * hls::expf(x);

                // payoff calculated based on European options
                float payoff = fmaxf(ST - K, 0.0f);
                partial_sum[l] += payoff;
            }
        }
    }

    // final reduction, adding all 8-lane totals into one number (simultaneously)
    float sum = 0.0f; // intialize sum
    for (int l = 0; l < LANES; l++) {
#pragma HLS UNROLL
        sum += partial_sum[l];
    }

    sum_out[0] = sum; // final sum
}
