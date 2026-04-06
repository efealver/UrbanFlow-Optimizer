"""
serial_optimizer.py — Single-threaded baseline for the Parallel Traffic Flow Optimizer.
CENG 471 Parallel Computing — Term Project

Runs all three optimization phases sequentially in a single thread.
Used as the baseline for speedup measurement.
"""

import time
from typing import Dict, List, Any

from network import TrafficNetwork, Intersection, Road, Vehicle
from algorithms import optimize_signal, detect_congestion, compute_route


def run_serial(network: TrafficNetwork, verbose: bool = False) -> Dict[str, Any]:
    """
    Run all three optimization phases serially (single-threaded).

    Phases:
      1. Signal optimization — Webster's formula per intersection
      2. Congestion detection — flow/capacity ratio per road
      3. Route computation — Dijkstra's shortest path per vehicle

    Returns a results dictionary containing:
      - signal_results : dict mapping intersection_id → optimized_green
      - bottlenecks    : list of road_ids where congestion >= 0.8
      - route_stats    : dict with avg_wait, total_vehicles, routed_vehicles
      - phase_times    : dict with wall-clock time per phase (seconds)
    """
    phase_times: Dict[str, float] = {}

    # ------------------------------------------------------------------
    # Phase 1: Signal Optimization
    # ------------------------------------------------------------------
    t0 = time.perf_counter()

    signal_results: Dict[int, float] = {}
    for intr in network.intersections.values():
        optimize_signal(intr)
        signal_results[intr.id] = intr.optimized_green

    phase_times["signal"] = time.perf_counter() - t0

    if verbose:
        print(f"  [Serial] Phase 1 (signal opt):   {phase_times['signal']:.4f}s "
              f"({len(signal_results)} intersections)")

    # ------------------------------------------------------------------
    # Phase 2: Congestion Detection
    # ------------------------------------------------------------------
    t0 = time.perf_counter()

    bottlenecks: List[int] = []
    for road in network.roads.values():
        if detect_congestion(road):
            bottlenecks.append(road.id)

    phase_times["congestion"] = time.perf_counter() - t0

    if verbose:
        print(f"  [Serial] Phase 2 (congestion):   {phase_times['congestion']:.4f}s "
              f"({len(bottlenecks)} bottlenecks / {len(network.roads)} roads)")

    # ------------------------------------------------------------------
    # Phase 3: Route Computation
    # ------------------------------------------------------------------
    t0 = time.perf_counter()

    for vehicle in network.vehicles:
        compute_route(vehicle, network)

    phase_times["routing"] = time.perf_counter() - t0

    routed = sum(1 for v in network.vehicles if len(v.route) > 0)
    total_wait = sum(v.total_wait for v in network.vehicles if len(v.route) > 0)
    avg_wait = total_wait / routed if routed > 0 else 0.0

    route_stats = {
        "total_vehicles": len(network.vehicles),
        "routed_vehicles": routed,
        "avg_wait": avg_wait,
        "total_wait": total_wait,
    }

    if verbose:
        print(f"  [Serial] Phase 3 (routing):      {phase_times['routing']:.4f}s "
              f"({routed}/{len(network.vehicles)} vehicles routed, "
              f"avg_wait={avg_wait:.1f}s)")

    total_time = sum(phase_times.values())
    if verbose:
        print(f"  [Serial] Total time: {total_time:.4f}s")

    return {
        "signal_results": signal_results,
        "bottlenecks": bottlenecks,
        "route_stats": route_stats,
        "phase_times": phase_times,
        "total_time": total_time,
    }
