"""
algorithms.py — Core algorithms for the Parallel Traffic Flow Optimizer.
CENG 471 Parallel Computing — Term Project

Implements:
  1. Webster's signal optimization formula
  2. Congestion detection (flow/capacity ratio)
  3. Dijkstra's shortest path with congestion-weighted edges
"""

import heapq
from typing import Dict, List, Optional, Tuple

from network import Intersection, Road, Vehicle, TrafficNetwork


# ---------------------------------------------------------------------------
# 1. Signal Optimization — Webster's Formula
# ---------------------------------------------------------------------------

def optimize_signal(intr: Intersection) -> None:
    """
    Apply Webster's formula to compute the optimal green time for an intersection.

    Webster's formula:
        C = (1.5 * L + 5) / (1 - Y)
        L = total lost time per cycle (fixed at 4 s)
        Y = critical flow ratio = vehicle_count / 100  (capped at 0.9)

    Green time per phase:
        g = C * (vehicle_count / total_demand)
        g = clamp(g, 10, 80)  seconds

    Wait time estimate:
        wait = C / 2  (simplified uniform arrival model)
    """
    L = 4.0                                          # total lost time (seconds)
    Y = min(intr.vehicle_count / 100.0, 0.9)        # critical flow ratio
    total_demand = max(intr.vehicle_count, 1)

    if Y >= 1.0:
        Y = 0.9

    C = (1.5 * L + 5.0) / (1.0 - Y)                # optimal cycle length
    g = C * (intr.vehicle_count / total_demand)
    g = max(10.0, min(g, 80.0))                      # clamp to [10, 80] seconds

    intr.optimized_green = g
    intr.wait_time = C / 2.0


# ---------------------------------------------------------------------------
# 2. Congestion Detection
# ---------------------------------------------------------------------------

def detect_congestion(road: Road) -> bool:
    """
    Compute congestion ratio and flag bottlenecks.

    congestion_ratio = flow / capacity
    bottleneck       = congestion_ratio >= 0.8

    Updates road.congestion in place.
    Returns True if the road is a bottleneck.
    """
    if road.capacity <= 0:
        road.congestion = 0.0
        return False

    road.congestion = min(road.flow / road.capacity, 1.0)
    return road.congestion >= 0.8


# ---------------------------------------------------------------------------
# 3. Shortest Path Routing — Dijkstra's Algorithm
# ---------------------------------------------------------------------------

def dijkstra(
    network: TrafficNetwork,
    source: int,
    dest: int,
) -> Tuple[List[int], float]:
    """
    Standard Dijkstra's shortest path with congestion-weighted edges.

    Edge weight: travel_time * (1 + congestion_ratio)

    Returns:
        (path, total_cost)  — path is a list of intersection IDs.
        If unreachable, returns ([], float('inf')).
    """
    dist: Dict[int, float] = {nid: float("inf") for nid in network.intersections}
    prev: Dict[int, Optional[int]] = {nid: None for nid in network.intersections}
    dist[source] = 0.0

    # Priority queue: (cost, intersection_id)
    pq: List[Tuple[float, int]] = [(0.0, source)]

    while pq:
        cost, u = heapq.heappop(pq)

        if cost > dist[u]:
            continue

        if u == dest:
            break

        for road_id in network.adjacency.get(u, []):
            road = network.roads[road_id]
            v = road.dest

            weight = road.travel_time * (1.0 + road.congestion)
            new_cost = dist[u] + weight

            if new_cost < dist[v]:
                dist[v] = new_cost
                prev[v] = u
                heapq.heappush(pq, (new_cost, v))

    # Reconstruct path
    if dist[dest] == float("inf"):
        return [], float("inf")

    path: List[int] = []
    cur: Optional[int] = dest
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    path.reverse()

    return path, dist[dest]


def compute_route(vehicle: Vehicle, network: TrafficNetwork) -> None:
    """
    Compute the optimal route for a vehicle using Dijkstra's algorithm.
    Updates vehicle.route and vehicle.total_wait in place.

    This function is designed to be called from multiple threads simultaneously;
    it only reads network.roads/adjacency (which are stable during routing)
    and writes only to the vehicle object passed to it.
    """
    path, cost = dijkstra(network, vehicle.source, vehicle.dest)
    vehicle.route = path
    vehicle.total_wait = cost if cost != float("inf") else 0.0
