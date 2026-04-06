"""
network.py — Traffic network data structures for the Parallel Traffic Flow Optimizer.
CENG 471 Parallel Computing — Term Project
"""

import threading
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Intersection:
    id: int
    x: float                   # grid position
    y: float
    vehicle_count: int         # current vehicles queued
    green_time: float          # current green signal duration (seconds)
    red_time: float
    optimized_green: float     # result after optimization
    wait_time: float           # estimated average wait
    lock: threading.Lock = field(default_factory=threading.Lock)

    def __repr__(self):
        return (f"Intersection(id={self.id}, pos=({self.x},{self.y}), "
                f"vehicles={self.vehicle_count}, green={self.green_time:.1f}s, "
                f"opt_green={self.optimized_green:.1f}s)")


@dataclass
class Road:
    id: int
    source: int                # source intersection id
    dest: int                  # destination intersection id
    capacity: int              # max vehicle capacity
    flow: int                  # current vehicle count
    congestion: float          # flow / capacity ratio (0.0–1.0)
    travel_time: float         # base travel time in seconds
    lock: threading.Lock = field(default_factory=threading.Lock)

    def __repr__(self):
        return (f"Road(id={self.id}, {self.source}->{self.dest}, "
                f"flow={self.flow}/{self.capacity}, congestion={self.congestion:.2f})")


@dataclass
class Vehicle:
    id: int
    source: int
    dest: int
    route: List[int]           # list of intersection IDs forming the path
    total_wait: float          # total estimated wait along route

    def __repr__(self):
        return (f"Vehicle(id={self.id}, {self.source}->{self.dest}, "
                f"route_len={len(self.route)}, wait={self.total_wait:.1f}s)")


class TrafficNetwork:
    def __init__(self):
        self.intersections: Dict[int, Intersection] = {}
        self.roads: Dict[int, Road] = {}
        self.adjacency: Dict[int, List[int]] = {}   # intersection_id → list of road_ids
        self.vehicles: List[Vehicle] = []

    def build_grid(self, side: int):
        """Build an N×N grid traffic network."""
        self.intersections.clear()
        self.roads.clear()
        self.adjacency.clear()
        self.vehicles.clear()

        n = side * side
        road_id = 0

        # Create intersections
        for i in range(side):
            for j in range(side):
                iid = i * side + j
                self.intersections[iid] = Intersection(
                    id=iid,
                    x=float(j),
                    y=float(i),
                    vehicle_count=random.randint(0, 50),
                    green_time=random.uniform(20.0, 60.0),
                    red_time=random.uniform(20.0, 60.0),
                    optimized_green=0.0,
                    wait_time=0.0,
                )
                self.adjacency[iid] = []

        # Create roads (bidirectional edges between adjacent grid nodes)
        for i in range(side):
            for j in range(side):
                src = i * side + j

                # Right neighbor
                if j + 1 < side:
                    dst = i * side + (j + 1)
                    cap = random.randint(50, 150)
                    flow = random.randint(0, cap)
                    self._add_road(road_id, src, dst, cap, flow)
                    road_id += 1
                    self._add_road(road_id, dst, src, cap, random.randint(0, cap))
                    road_id += 1

                # Down neighbor
                if i + 1 < side:
                    dst = (i + 1) * side + j
                    cap = random.randint(50, 150)
                    flow = random.randint(0, cap)
                    self._add_road(road_id, src, dst, cap, flow)
                    road_id += 1
                    self._add_road(road_id, dst, src, cap, random.randint(0, cap))
                    road_id += 1

    def _add_road(self, rid: int, src: int, dst: int, cap: int, flow: int):
        flow = min(flow, cap)
        congestion = flow / cap if cap > 0 else 0.0
        travel_time = random.uniform(30.0, 120.0)
        road = Road(
            id=rid,
            source=src,
            dest=dst,
            capacity=cap,
            flow=flow,
            congestion=congestion,
            travel_time=travel_time,
        )
        self.roads[rid] = road
        self.adjacency[src].append(rid)

    def generate_vehicles(self, count: int):
        """Generate vehicles with random source and destination intersections."""
        self.vehicles.clear()
        iids = list(self.intersections.keys())
        if len(iids) < 2:
            return

        for i in range(count):
            src, dst = random.sample(iids, 2)
            self.vehicles.append(Vehicle(
                id=i,
                source=src,
                dest=dst,
                route=[],
                total_wait=0.0,
            ))

    def summary(self) -> str:
        n_int = len(self.intersections)
        n_road = len(self.roads)
        n_veh = len(self.vehicles)
        avg_cong = (sum(r.congestion for r in self.roads.values()) / n_road
                    if n_road else 0.0)
        return (f"Network: {n_int} intersections, {n_road} roads, "
                f"{n_veh} vehicles, avg_congestion={avg_cong:.2f}")
