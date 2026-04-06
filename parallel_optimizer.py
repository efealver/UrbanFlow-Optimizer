"""
parallel_optimizer.py — Multi-threaded implementation of the Traffic Flow Optimizer.
CENG 471 Parallel Computing — Term Project

Synchronization primitives used:
  - threading.Lock    : per Intersection, per Road, and global results lists
  - threading.Barrier : phase synchronization for SignalOptimizer threads
  - queue.Queue       : thread-safe statistics aggregation for routing
"""

import threading
import queue
import time
from typing import Dict, List, Any, Optional

from network import TrafficNetwork, Intersection, Road, Vehicle
from algorithms import optimize_signal, detect_congestion, compute_route


# ---------------------------------------------------------------------------
# Workload Partitioning
# ---------------------------------------------------------------------------

def partition(items: list, num_threads: int) -> List[list]:
    """
    Split items into num_threads roughly equal chunks.
    The last chunk absorbs any remainder.
    """
    if num_threads <= 0:
        return [items]
    n = len(items)
    chunk = max(1, n // num_threads)
    parts = []
    for i in range(num_threads):
        start = i * chunk
        # Last thread takes the remainder
        end = start + chunk if i < num_threads - 1 else n
        parts.append(items[start:end])
    return parts


# ---------------------------------------------------------------------------
# Thread Worker 1: Signal Optimization
# ---------------------------------------------------------------------------

class SignalOptimizer(threading.Thread):
    """
    Applies Webster's formula to a subset of intersections.

    Synchronization:
      - barrier: all signal threads rendezvous before writing aggregated results
      - global_lock: protects the shared signal_results dict
      - Per-intersection lock is acquired before writing optimized_green / wait_time
    """

    def __init__(
        self,
        thread_id: int,
        intersections: List[Intersection],
        signal_results: Dict[int, float],
        global_lock: threading.Lock,
        barrier: threading.Barrier,
        verbose: bool = False,
    ):
        super().__init__(name=f"SignalOptimizer-{thread_id}")
        self.thread_id = thread_id
        self.intersections = intersections
        self.signal_results = signal_results
        self.global_lock = global_lock
        self.barrier = barrier
        self.verbose = verbose
        self.elapsed: float = 0.0

    def run(self):
        t0 = time.perf_counter()

        # Compute locally; each intersection object is thread-safe via its own lock
        local_results: Dict[int, float] = {}
        for intr in self.intersections:
            with intr.lock:
                optimize_signal(intr)
                local_results[intr.id] = intr.optimized_green

        # Wait for all signal threads to finish computing before aggregating
        self.barrier.wait()

        # Merge local results into shared dict under global lock
        with self.global_lock:
            self.signal_results.update(local_results)

        self.elapsed = time.perf_counter() - t0
        if self.verbose:
            print(f"  [{self.name}] processed {len(self.intersections)} intersections "
                  f"in {self.elapsed:.4f}s")


# ---------------------------------------------------------------------------
# Thread Worker 2: Congestion Detection
# ---------------------------------------------------------------------------

class CongestionDetector(threading.Thread):
    """
    Computes flow/capacity congestion ratio for a subset of roads.

    Synchronization:
      - Per-road lock is acquired before updating road.congestion
      - global_lock protects the shared bottlenecks list
    """

    def __init__(
        self,
        thread_id: int,
        roads: List[Road],
        bottlenecks: List[int],
        global_lock: threading.Lock,
        verbose: bool = False,
    ):
        super().__init__(name=f"CongestionDetector-{thread_id}")
        self.thread_id = thread_id
        self.roads = roads
        self.bottlenecks = bottlenecks
        self.global_lock = global_lock
        self.verbose = verbose
        self.elapsed: float = 0.0

    def run(self):
        t0 = time.perf_counter()

        local_bottlenecks: List[int] = []
        for road in self.roads:
            with road.lock:
                is_bottleneck = detect_congestion(road)
            if is_bottleneck:
                local_bottlenecks.append(road.id)

        with self.global_lock:
            self.bottlenecks.extend(local_bottlenecks)

        self.elapsed = time.perf_counter() - t0
        if self.verbose:
            print(f"  [{self.name}] processed {len(self.roads)} roads, "
                  f"{len(local_bottlenecks)} bottlenecks in {self.elapsed:.4f}s")


# ---------------------------------------------------------------------------
# Thread Worker 3: Route Flow Computation
# ---------------------------------------------------------------------------

class RouteFlowComputer(threading.Thread):
    """
    Computes Dijkstra routes for a subset of vehicles and updates road flows.

    Synchronization:
      - Per-road lock is acquired when updating road.flow after routing
      - stats_q (queue.Queue) collects per-thread statistics thread-safely
    """

    def __init__(
        self,
        thread_id: int,
        vehicles: List[Vehicle],
        network: TrafficNetwork,
        global_lock: threading.Lock,
        stats_q: queue.Queue,
        verbose: bool = False,
    ):
        super().__init__(name=f"RouteFlowComputer-{thread_id}")
        self.thread_id = thread_id
        self.vehicles = vehicles
        self.network = network
        self.global_lock = global_lock
        self.stats_q = stats_q
        self.verbose = verbose
        self.elapsed: float = 0.0

    def run(self):
        t0 = time.perf_counter()

        routed = 0
        total_wait = 0.0

        for vehicle in self.vehicles:
            compute_route(vehicle, self.network)

            # Update road flows along the computed route (requires per-road lock)
            if len(vehicle.route) >= 2:
                routed += 1
                total_wait += vehicle.total_wait
                self._update_road_flows(vehicle)

        self.elapsed = time.perf_counter() - t0

        self.stats_q.put({
            "thread_id": self.thread_id,
            "routed": routed,
            "total_wait": total_wait,
            "elapsed": self.elapsed,
        })

        if self.verbose:
            print(f"  [{self.name}] routed {routed}/{len(self.vehicles)} vehicles "
                  f"in {self.elapsed:.4f}s")

    def _update_road_flows(self, vehicle: Vehicle):
        """Increment flow on each road traversed by this vehicle."""
        route = vehicle.route
        for i in range(len(route) - 1):
            u, v = route[i], route[i + 1]
            # Find the road connecting u → v
            for road_id in self.network.adjacency.get(u, []):
                road = self.network.roads[road_id]
                if road.dest == v:
                    with road.lock:
                        road.flow = min(road.flow + 1, road.capacity)
                        road.congestion = road.flow / road.capacity
                    break


# ---------------------------------------------------------------------------
# Main Parallel Run Function
# ---------------------------------------------------------------------------

def run_parallel(
    network: TrafficNetwork,
    num_threads: int,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Run all three optimization phases in parallel using num_threads threads.

    Returns the same structure as serial_optimizer.run_serial().
    """
    phase_times: Dict[str, float] = {}
    signal_results: Dict[int, float] = {}
    bottlenecks: List[int] = []
    global_lock = threading.Lock()

    intersections = list(network.intersections.values())
    roads = list(network.roads.values())
    vehicles = list(network.vehicles)

    # Clamp num_threads to available work
    nt_signal = min(num_threads, max(1, len(intersections)))
    nt_cong = min(num_threads, max(1, len(roads)))
    nt_route = min(num_threads, max(1, len(vehicles)))

    # ------------------------------------------------------------------
    # Phase 1: Signal Optimization
    # ------------------------------------------------------------------
    t0 = time.perf_counter()

    barrier = threading.Barrier(nt_signal)
    int_parts = partition(intersections, nt_signal)

    signal_threads = [
        SignalOptimizer(
            i, int_parts[i], signal_results, global_lock, barrier, verbose
        )
        for i in range(nt_signal)
    ]
    for t in signal_threads:
        t.start()
    for t in signal_threads:
        t.join()

    phase_times["signal"] = time.perf_counter() - t0

    if verbose:
        print(f"  [Parallel] Phase 1 (signal opt): {phase_times['signal']:.4f}s "
              f"({nt_signal} threads, {len(intersections)} intersections)")

    # ------------------------------------------------------------------
    # Phase 2: Congestion Detection
    # ------------------------------------------------------------------
    t0 = time.perf_counter()

    road_parts = partition(roads, nt_cong)

    congestion_threads = [
        CongestionDetector(i, road_parts[i], bottlenecks, global_lock, verbose)
        for i in range(nt_cong)
    ]
    for t in congestion_threads:
        t.start()
    for t in congestion_threads:
        t.join()

    phase_times["congestion"] = time.perf_counter() - t0

    if verbose:
        print(f"  [Parallel] Phase 2 (congestion): {phase_times['congestion']:.4f}s "
              f"({nt_cong} threads, {len(bottlenecks)} bottlenecks)")

    # ------------------------------------------------------------------
    # Phase 3: Route Computation
    # ------------------------------------------------------------------
    t0 = time.perf_counter()

    stats_q: queue.Queue = queue.Queue()
    veh_parts = partition(vehicles, nt_route)

    route_threads = [
        RouteFlowComputer(i, veh_parts[i], network, global_lock, stats_q, verbose)
        for i in range(nt_route)
    ]
    for t in route_threads:
        t.start()
    for t in route_threads:
        t.join()

    phase_times["routing"] = time.perf_counter() - t0

    # Collect routing stats from queue
    total_routed = 0
    total_wait = 0.0
    while not stats_q.empty():
        s = stats_q.get_nowait()
        total_routed += s["routed"]
        total_wait += s["total_wait"]

    avg_wait = total_wait / total_routed if total_routed > 0 else 0.0
    route_stats = {
        "total_vehicles": len(vehicles),
        "routed_vehicles": total_routed,
        "avg_wait": avg_wait,
        "total_wait": total_wait,
    }

    if verbose:
        print(f"  [Parallel] Phase 3 (routing):    {phase_times['routing']:.4f}s "
              f"({nt_route} threads, {total_routed}/{len(vehicles)} routed, "
              f"avg_wait={avg_wait:.1f}s)")

    total_time = sum(phase_times.values())
    if verbose:
        print(f"  [Parallel] Total time: {total_time:.4f}s")

    return {
        "signal_results": signal_results,
        "bottlenecks": bottlenecks,
        "route_stats": route_stats,
        "phase_times": phase_times,
        "total_time": total_time,
        "num_threads": num_threads,
    }
