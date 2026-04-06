"""
visualize.py — Generate charts and visualizations for the Traffic Flow Optimizer.
CENG 471 Parallel Computing — Term Project

Generates:
  1. Speedup vs Thread Count
  2. Execution Time vs Network Size
  3. Congestion Heatmap
  4. Signal Optimization Before/After
  5. Efficiency vs Thread Count
"""

import json
import math
import os
from typing import Dict, List, Any, Optional

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for saving files
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

from network import TrafficNetwork


SCREENSHOTS_DIR = "screenshots"
RESULTS_FILE = "benchmark_results.json"


def _ensure_dir():
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# 1. Speedup vs Thread Count
# ---------------------------------------------------------------------------

def plot_speedup(results: List[Dict[str, Any]], output_dir: str = SCREENSHOTS_DIR):
    """Line plot: Speedup vs Thread Count, one line per network size."""
    _ensure_dir()

    fig, ax = plt.subplots(figsize=(10, 6))

    # Group results by network size
    by_size: Dict[int, Dict] = {}
    for entry in results:
        n = entry["n_intersections"]
        if n not in by_size:
            by_size[n] = entry

    thread_counts = sorted({p["num_threads"] for e in results for p in e["parallel"]})

    for n, entry in sorted(by_size.items()):
        speedups = []
        threads = []
        for par in sorted(entry["parallel"], key=lambda x: x["num_threads"]):
            threads.append(par["num_threads"])
            speedups.append(par["speedup"])
        ax.plot(threads, speedups, marker="o", label=f"{n} intersections")

    # Ideal linear speedup reference
    ax.plot(thread_counts, thread_counts, "k--", alpha=0.4, label="Ideal (linear)")

    ax.set_xlabel("Number of Threads", fontsize=12)
    ax.set_ylabel("Speedup S(T) = T_serial / T_parallel", fontsize=12)
    ax.set_title("Speedup vs Thread Count", fontsize=14, fontweight="bold")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_xticks(thread_counts)

    path = os.path.join(output_dir, "speedup_vs_threads.png")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"[Visualize] Saved: {path}")


# ---------------------------------------------------------------------------
# 2. Execution Time vs Network Size
# ---------------------------------------------------------------------------

def plot_execution_time(results: List[Dict[str, Any]], output_dir: str = SCREENSHOTS_DIR):
    """Bar chart: Serial vs Parallel (4 threads) execution time vs network size."""
    _ensure_dir()

    # Use the largest vehicle count available for this chart
    max_veh = max(e["n_vehicles"] for e in results)
    subset = [e for e in results if e["n_vehicles"] == max_veh]
    subset.sort(key=lambda e: e["n_intersections"])

    sizes = [e["n_intersections"] for e in subset]
    serial_times = [e["serial_time"] for e in subset]

    target_threads = 4
    parallel_times = []
    for e in subset:
        candidates = [p for p in e["parallel"] if p["num_threads"] == target_threads]
        if candidates:
            parallel_times.append(candidates[0]["parallel_time"])
        else:
            parallel_times.append(None)

    x = np.arange(len(sizes))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    bars1 = ax.bar(x - width/2, serial_times, width, label="Serial", color="#e74c3c", alpha=0.85)
    bars2 = ax.bar(
        x + width/2,
        [t if t is not None else 0 for t in parallel_times],
        width,
        label=f"Parallel ({target_threads} threads)",
        color="#2ecc71",
        alpha=0.85,
    )

    ax.set_xlabel("Network Size (intersections)", fontsize=12)
    ax.set_ylabel("Execution Time (seconds)", fontsize=12)
    ax.set_title(f"Execution Time vs Network Size ({max_veh} vehicles)", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(sizes)
    ax.legend(fontsize=11)
    ax.grid(True, axis="y", alpha=0.3)

    path = os.path.join(output_dir, "execution_time_vs_size.png")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"[Visualize] Saved: {path}")


# ---------------------------------------------------------------------------
# 3. Congestion Heatmap
# ---------------------------------------------------------------------------

def plot_congestion_heatmap(network: TrafficNetwork, output_dir: str = SCREENSHOTS_DIR):
    """
    Render the traffic network grid with roads color-coded by congestion ratio.
    Green = free flow, Red = congested.
    """
    _ensure_dir()

    side = round(math.sqrt(len(network.intersections)))

    fig, ax = plt.subplots(figsize=(8, 8))
    cmap = plt.cm.RdYlGn_r  # Red=high congestion, Green=low

    # Draw roads
    for road in network.roads.values():
        src = network.intersections[road.source]
        dst = network.intersections[road.dest]
        color = cmap(road.congestion)
        ax.plot(
            [src.x, dst.x], [src.y, dst.y],
            color=color, linewidth=2.5, alpha=0.8,
        )

    # Draw intersections
    for intr in network.intersections.values():
        ax.scatter(intr.x, intr.y, s=80, color="#2c3e50", zorder=5)

    # Colorbar
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=mcolors.Normalize(0, 1))
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Congestion Ratio (flow/capacity)", fontsize=11)

    ax.set_title("Traffic Congestion Heatmap", fontsize=14, fontweight="bold")
    ax.set_xlabel("Grid X")
    ax.set_ylabel("Grid Y")
    ax.set_aspect("equal")

    path = os.path.join(output_dir, "congestion_heatmap.png")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"[Visualize] Saved: {path}")


# ---------------------------------------------------------------------------
# 4. Signal Optimization Before/After
# ---------------------------------------------------------------------------

def plot_signal_optimization(network: TrafficNetwork, output_dir: str = SCREENSHOTS_DIR):
    """Bar chart: green times before vs after optimization (sample of intersections)."""
    _ensure_dir()

    intersections = list(network.intersections.values())
    # Sample up to 15 for readability
    sample = intersections[:min(15, len(intersections))]

    ids = [f"I{i.id}" for i in sample]
    before = [i.green_time for i in sample]
    after = [i.optimized_green for i in sample]

    x = np.arange(len(ids))
    width = 0.35

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(x - width/2, before, width, label="Before (original)", color="#3498db", alpha=0.85)
    ax.bar(x + width/2, after, width, label="After (Webster's)", color="#e67e22", alpha=0.85)

    ax.set_xlabel("Intersection ID", fontsize=12)
    ax.set_ylabel("Green Time (seconds)", fontsize=12)
    ax.set_title("Signal Optimization: Before vs After", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(ids, rotation=45, ha="right")
    ax.legend(fontsize=11)
    ax.grid(True, axis="y", alpha=0.3)

    path = os.path.join(output_dir, "signal_optimization.png")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"[Visualize] Saved: {path}")


# ---------------------------------------------------------------------------
# 5. Efficiency vs Thread Count
# ---------------------------------------------------------------------------

def plot_efficiency(results: List[Dict[str, Any]], output_dir: str = SCREENSHOTS_DIR):
    """Line plot: Efficiency E(T) = S(T)/T vs Thread Count."""
    _ensure_dir()

    fig, ax = plt.subplots(figsize=(10, 6))

    by_size: Dict[int, Dict] = {}
    for entry in results:
        n = entry["n_intersections"]
        if n not in by_size:
            by_size[n] = entry

    thread_counts = sorted({p["num_threads"] for e in results for p in e["parallel"]})

    for n, entry in sorted(by_size.items()):
        efficiencies = []
        threads = []
        for par in sorted(entry["parallel"], key=lambda x: x["num_threads"]):
            threads.append(par["num_threads"])
            efficiencies.append(par["efficiency"])
        ax.plot(threads, efficiencies, marker="s", label=f"{n} intersections")

    ax.axhline(y=1.0, color="k", linestyle="--", alpha=0.4, label="Ideal (E=1.0)")

    ax.set_xlabel("Number of Threads", fontsize=12)
    ax.set_ylabel("Efficiency E(T) = S(T) / T", fontsize=12)
    ax.set_title("Parallel Efficiency vs Thread Count", fontsize=14, fontweight="bold")
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_xticks(thread_counts)
    ax.set_ylim(0, 1.5)

    path = os.path.join(output_dir, "efficiency_vs_threads.png")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"[Visualize] Saved: {path}")


# ---------------------------------------------------------------------------
# Generate all visualizations
# ---------------------------------------------------------------------------

def generate_all(network: Optional[TrafficNetwork] = None, results_file: str = RESULTS_FILE):
    """Load benchmark results and generate all charts."""
    try:
        with open(results_file) as f:
            results = json.load(f)
        print(f"[Visualize] Loaded {len(results)} benchmark entries from {results_file}")
    except FileNotFoundError:
        print(f"[Visualize] {results_file} not found — skipping benchmark charts.")
        results = []

    if results:
        plot_speedup(results)
        plot_execution_time(results)
        plot_efficiency(results)

    if network is not None:
        plot_congestion_heatmap(network)
        plot_signal_optimization(network)

    print(f"[Visualize] All charts saved to {SCREENSHOTS_DIR}/")


if __name__ == "__main__":
    import random
    random.seed(42)
    net = TrafficNetwork()
    net.build_grid(8)
    net.generate_vehicles(200)

    # Run serial to populate optimized_green
    from serial_optimizer import run_serial
    run_serial(net)

    generate_all(network=net)
