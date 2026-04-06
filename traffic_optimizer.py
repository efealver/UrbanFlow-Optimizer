"""
traffic_optimizer.py — Main entry point for the Parallel Traffic Flow Optimizer.
CENG 471 Parallel Computing — Term Project

Usage:
    python traffic_optimizer.py [OPTIONS]

Options:
    --mode      serial | parallel | benchmark | all   (default: all)
    --threads   number of threads                      (default: 4)
    --grid      grid side length (NxN grid)            (default: 8)
    --vehicles  number of vehicles                     (default: 200)
    --verbose   print per-thread timing info

Examples:
    python traffic_optimizer.py --mode all --threads 4 --grid 8
    python traffic_optimizer.py --mode benchmark
    python traffic_optimizer.py --mode parallel --threads 8 --grid 10 --verbose
"""

import argparse
import random
import sys
import time

from network import TrafficNetwork
from serial_optimizer import run_serial
from parallel_optimizer import run_parallel


BANNER = """
╔══════════════════════════════════════════════════════════════╗
║         Parallel Traffic Flow Optimizer                      ║
║         CENG 471 Parallel Computing — Term Project           ║
╚══════════════════════════════════════════════════════════════╝
"""


def print_results(label: str, result: dict):
    print(f"\n  ── {label} Results ──────────────────────────────")
    print(f"  Total time         : {result['total_time']:.4f}s")
    pt = result["phase_times"]
    print(f"  Phase 1 (signals)  : {pt['signal']:.4f}s")
    print(f"  Phase 2 (congestion): {pt['congestion']:.4f}s")
    print(f"  Phase 3 (routing)  : {pt['routing']:.4f}s")
    rs = result["route_stats"]
    print(f"  Bottleneck roads   : {len(result['bottlenecks'])}")
    print(f"  Vehicles routed    : {rs['routed_vehicles']}/{rs['total_vehicles']}")
    print(f"  Avg vehicle wait   : {rs['avg_wait']:.1f}s")


def run_mode_serial(net: TrafficNetwork, verbose: bool):
    print("\n[Mode: SERIAL]")
    result = run_serial(net, verbose=verbose)
    print_results("Serial", result)
    return result


def run_mode_parallel(net: TrafficNetwork, num_threads: int, verbose: bool):
    print(f"\n[Mode: PARALLEL — {num_threads} threads]")
    result = run_parallel(net, num_threads=num_threads, verbose=verbose)
    print_results(f"Parallel ({num_threads}T)", result)
    return result


def run_mode_all(net: TrafficNetwork, num_threads: int, verbose: bool):
    print("\n[Mode: ALL — Serial + Parallel Comparison]")

    # Serial
    net_s = _copy_network(net)
    t0 = time.perf_counter()
    serial_result = run_serial(net_s, verbose=verbose)
    serial_time = time.perf_counter() - t0
    print_results("Serial", serial_result)

    # Parallel
    net_p = _copy_network(net)
    t0 = time.perf_counter()
    par_result = run_parallel(net_p, num_threads=num_threads, verbose=verbose)
    par_time = time.perf_counter() - t0
    print_results(f"Parallel ({num_threads}T)", par_result)

    # Comparison
    speedup = serial_time / par_time if par_time > 0 else float("inf")
    efficiency = speedup / num_threads
    print(f"\n  ── Performance Summary ──────────────────────────")
    print(f"  Serial time        : {serial_time:.4f}s")
    print(f"  Parallel time      : {par_time:.4f}s  ({num_threads} threads)")
    print(f"  Speedup S(T)       : {speedup:.3f}x")
    print(f"  Efficiency E(T)    : {efficiency:.3f}")

    return serial_result, par_result


def run_mode_benchmark(verbose: bool):
    print("\n[Mode: BENCHMARK]")
    print("  This may take several minutes depending on machine speed...\n")
    from benchmark import run_full_benchmark, print_summary_table
    results = run_full_benchmark(verbose=verbose)
    print_summary_table(results)

    print("\n  Generating visualizations...")
    try:
        from visualize import generate_all
        generate_all()
    except ImportError as e:
        print(f"  [Warning] Could not generate charts: {e}")


def _copy_network(net: TrafficNetwork) -> TrafficNetwork:
    """
    Build a fresh network with the same dimensions and same random seed
    so both serial and parallel run on identical data.
    We re-seed before building to get the same data every time.
    """
    import copy
    # Deep copy: dataclasses with Locks are not pickle-able, so we use copy
    new_net = TrafficNetwork()
    new_net.intersections = {
        k: _copy_intersection(v) for k, v in net.intersections.items()
    }
    new_net.roads = {k: _copy_road(v) for k, v in net.roads.items()}
    new_net.adjacency = {k: list(v) for k, v in net.adjacency.items()}
    new_net.vehicles = [_copy_vehicle(v) for v in net.vehicles]
    return new_net


def _copy_intersection(i):
    from network import Intersection
    import threading
    return Intersection(
        id=i.id, x=i.x, y=i.y,
        vehicle_count=i.vehicle_count,
        green_time=i.green_time, red_time=i.red_time,
        optimized_green=0.0, wait_time=0.0,
    )


def _copy_road(r):
    from network import Road
    return Road(
        id=r.id, source=r.source, dest=r.dest,
        capacity=r.capacity, flow=r.flow,
        congestion=r.congestion, travel_time=r.travel_time,
    )


def _copy_vehicle(v):
    from network import Vehicle
    return Vehicle(id=v.id, source=v.source, dest=v.dest, route=[], total_wait=0.0)


def verify_correctness(serial_result: dict, par_result: dict, tolerance: float = 0.01):
    """Basic sanity checks between serial and parallel results."""
    issues = []

    s_bn = set(serial_result["bottlenecks"])
    p_bn = set(par_result["bottlenecks"])
    if s_bn != p_bn:
        issues.append(f"Bottleneck mismatch: serial={len(s_bn)}, parallel={len(p_bn)}")

    s_sig = serial_result["signal_results"]
    p_sig = par_result["signal_results"]
    mismatched_signals = 0
    for iid in s_sig:
        if iid in p_sig:
            if abs(s_sig[iid] - p_sig[iid]) > tolerance:
                mismatched_signals += 1
    if mismatched_signals:
        issues.append(f"Signal mismatch in {mismatched_signals} intersections")

    if issues:
        print("\n  [Correctness] WARNINGS:")
        for issue in issues:
            print(f"    - {issue}")
    else:
        print("\n  [Correctness] All checks passed.")


def main():
    parser = argparse.ArgumentParser(
        description="Parallel Traffic Flow Optimizer — CENG 471",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--mode", choices=["serial", "parallel", "benchmark", "all"],
                        default="all", help="Run mode (default: all)")
    parser.add_argument("--threads", type=int, default=4,
                        help="Number of parallel threads (default: 4)")
    parser.add_argument("--grid", type=int, default=8,
                        help="Grid side length N (creates N×N network, default: 8)")
    parser.add_argument("--vehicles", type=int, default=200,
                        help="Number of vehicles (default: 200)")
    parser.add_argument("--verbose", action="store_true",
                        help="Print per-thread timing info")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility (default: 42)")
    args = parser.parse_args()

    print(BANNER)
    print(f"  Grid     : {args.grid}×{args.grid} = {args.grid**2} intersections")
    print(f"  Vehicles : {args.vehicles}")
    print(f"  Threads  : {args.threads}")
    print(f"  Mode     : {args.mode}")
    print(f"  Seed     : {args.seed}")

    if args.mode == "benchmark":
        run_mode_benchmark(verbose=args.verbose)
        return

    # Build network
    random.seed(args.seed)
    net = TrafficNetwork()
    net.build_grid(args.grid)
    net.generate_vehicles(args.vehicles)
    print(f"\n  {net.summary()}")

    if args.mode == "serial":
        run_mode_serial(net, verbose=args.verbose)

    elif args.mode == "parallel":
        run_mode_parallel(net, num_threads=args.threads, verbose=args.verbose)

    elif args.mode == "all":
        serial_result, par_result = run_mode_all(net, num_threads=args.threads,
                                                  verbose=args.verbose)
        verify_correctness(serial_result, par_result)

        print("\n  Generating visualizations...")
        try:
            from visualize import plot_congestion_heatmap, plot_signal_optimization
            # Use a fresh serial-run network for visualization
            random.seed(args.seed)
            vis_net = TrafficNetwork()
            vis_net.build_grid(args.grid)
            vis_net.generate_vehicles(args.vehicles)
            run_serial(vis_net)
            plot_congestion_heatmap(vis_net)
            plot_signal_optimization(vis_net)
            print("  Visualizations saved to screenshots/")
        except Exception as e:
            print(f"  [Warning] Could not generate visualizations: {e}")

    print("\nDone.\n")


if __name__ == "__main__":
    main()
