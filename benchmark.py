"""
benchmark.py — Benchmarks serial vs parallel Traffic Flow Optimizer.
CENG 471 Parallel Computing — Term Project

Sweeps over network sizes, thread counts, and vehicle counts.
Saves results to benchmark_results.json.
"""

import json
import random
import time
from typing import Dict, Any, List

from network import TrafficNetwork
from serial_optimizer import run_serial
from parallel_optimizer import run_parallel


# Default sweep configurations
CONFIGS = {
    "network_sizes": [16, 25, 36, 49, 64],   # N×N grid (side = sqrt(N))
    "thread_counts": [1, 2, 4, 8, 16],
    "vehicle_counts": [50, 100, 200],
}

RESULTS_FILE = "benchmark_results.json"
RANDOM_SEED = 42


def _side(n: int) -> int:
    """Return the grid side length for N total intersections (nearest integer sqrt)."""
    import math
    return max(2, round(math.sqrt(n)))


def build_network(n_intersections: int, n_vehicles: int, seed: int) -> TrafficNetwork:
    random.seed(seed)
    net = TrafficNetwork()
    net.build_grid(_side(n_intersections))
    net.generate_vehicles(n_vehicles)
    return net


def run_single_benchmark(
    n_intersections: int,
    n_vehicles: int,
    thread_counts: List[int],
    seed: int = RANDOM_SEED,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Run serial once and parallel for each thread count on the same network.

    Returns a dict with serial and parallel timing results.
    """
    entry: Dict[str, Any] = {
        "n_intersections": n_intersections,
        "n_vehicles": n_vehicles,
        "seed": seed,
    }

    # Serial run
    net = build_network(n_intersections, n_vehicles, seed)
    if verbose:
        print(f"\n[Benchmark] Serial — {net.summary()}")

    t0 = time.perf_counter()
    serial_result = run_serial(net, verbose=verbose)
    serial_time = time.perf_counter() - t0

    entry["serial_time"] = serial_time
    entry["serial_phase_times"] = serial_result["phase_times"]
    entry["serial_bottlenecks"] = len(serial_result["bottlenecks"])
    entry["serial_routed"] = serial_result["route_stats"]["routed_vehicles"]

    if verbose:
        print(f"  Serial total: {serial_time:.4f}s")

    # Parallel runs
    entry["parallel"] = []
    for nt in thread_counts:
        net = build_network(n_intersections, n_vehicles, seed)
        if verbose:
            print(f"\n[Benchmark] Parallel ({nt} threads) — {net.summary()}")

        t0 = time.perf_counter()
        par_result = run_parallel(net, num_threads=nt, verbose=verbose)
        par_time = time.perf_counter() - t0

        speedup = serial_time / par_time if par_time > 0 else float("inf")
        efficiency = speedup / nt

        par_entry = {
            "num_threads": nt,
            "parallel_time": par_time,
            "phase_times": par_result["phase_times"],
            "speedup": speedup,
            "efficiency": efficiency,
            "bottlenecks": len(par_result["bottlenecks"]),
            "routed": par_result["route_stats"]["routed_vehicles"],
        }
        entry["parallel"].append(par_entry)

        if verbose:
            print(f"  Parallel ({nt:2d} threads): {par_time:.4f}s  "
                  f"speedup={speedup:.2f}x  efficiency={efficiency:.2f}")

    return entry


def run_full_benchmark(
    configs: Dict[str, Any] = None,
    verbose: bool = True,
    output_file: str = RESULTS_FILE,
) -> List[Dict[str, Any]]:
    """
    Run the full benchmark sweep and save results to JSON.
    """
    if configs is None:
        configs = CONFIGS

    results: List[Dict[str, Any]] = []

    total = len(configs["network_sizes"]) * len(configs["vehicle_counts"])
    done = 0

    for n_int in configs["network_sizes"]:
        for n_veh in configs["vehicle_counts"]:
            done += 1
            print(f"\n{'='*60}")
            print(f"[{done}/{total}] Network size: {n_int} intersections, "
                  f"{n_veh} vehicles")
            print(f"{'='*60}")

            entry = run_single_benchmark(
                n_intersections=n_int,
                n_vehicles=n_veh,
                thread_counts=configs["thread_counts"],
                verbose=verbose,
            )
            results.append(entry)

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n[Benchmark] Results saved to {output_file}")
    return results


def print_summary_table(results: List[Dict[str, Any]]):
    """Print a formatted summary table of benchmark results."""
    print("\n" + "="*80)
    print(f"{'Network':>8} {'Vehicles':>8} {'Threads':>7} "
          f"{'Serial(s)':>10} {'Parallel(s)':>12} {'Speedup':>8} {'Efficiency':>10}")
    print("-"*80)

    for entry in results:
        n = entry["n_intersections"]
        v = entry["n_vehicles"]
        st = entry["serial_time"]
        for par in entry["parallel"]:
            nt = par["num_threads"]
            pt = par["parallel_time"]
            sp = par["speedup"]
            ef = par["efficiency"]
            print(f"{n:>8} {v:>8} {nt:>7} {st:>10.4f} {pt:>12.4f} "
                  f"{sp:>8.2f} {ef:>10.2f}")

    print("="*80)


if __name__ == "__main__":
    results = run_full_benchmark(verbose=True)
    print_summary_table(results)
