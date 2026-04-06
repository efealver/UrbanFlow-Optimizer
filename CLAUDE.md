# CLAUDE.md — Parallel Traffic Flow Optimizer
## CENG 471 Parallel Computing — Term Project

---

## PROJECT OVERVIEW

This project implements a **Parallel Traffic Flow Optimizer** in Python using the `threading` module (Pthreads equivalent). The core idea is to take a serial traffic simulation algorithm and parallelize it across multiple threads to demonstrate speedup, scalability, and correctness under concurrency.

The deliverables are:
1. A working Python codebase (serial + parallel versions)
2. A performance benchmark comparing serial vs parallel
3. A formatted Word (.docx) project report per course requirements
4. Screenshots of terminal output and performance graphs

---

## COURSE REQUIREMENTS CHECKLIST

- [x] Python implementation
- [x] Parallel implementation of a serial algorithm
- [x] Uses Pthreads (Python `threading` module — direct Pthreads wrapper via CPython)
- [x] Report: cover sheet with student name(s) and ID(s)
- [x] Report: introduction section describing the problem
- [x] Report: which group member did which part
- [x] Report: algorithms used
- [x] Report: code listings
- [x] Report: screenshots of the project running
- [x] Deadline: 27th April 2026 Monday

---

## PROJECT ARCHITECTURE

```
traffic_optimizer/
│
├── CLAUDE.md                  ← this file
├── traffic_optimizer.py       ← MAIN entry point
├── serial_optimizer.py        ← Serial (single-threaded) baseline
├── parallel_optimizer.py      ← Parallel (multi-threaded) implementation
├── network.py                 ← Traffic network data structures
├── algorithms.py              ← Core algorithms (Dijkstra, Webster, congestion)
├── benchmark.py               ← Benchmarks serial vs parallel, saves results
├── visualize.py               ← Generates charts (speedup, congestion maps)
├── generate_report.js         ← Generates the Word (.docx) project report
└── screenshots/               ← Terminal output screenshots for the report
```

---

## DATA STRUCTURES (network.py)

### Intersection
```python
@dataclass
class Intersection:
    id: int
    x: float                  # grid position
    y: float
    vehicle_count: int        # current vehicles queued
    green_time: float         # current green signal duration (seconds)
    red_time: float
    optimized_green: float    # result after optimization
    wait_time: float          # estimated average wait
    lock: threading.Lock      # per-intersection mutex for thread safety
```

### Road
```python
@dataclass
class Road:
    id: int
    source: int               # source intersection id
    dest: int                 # destination intersection id
    capacity: int             # max vehicle capacity
    flow: int                 # current vehicle count
    congestion: float         # flow / capacity ratio (0.0–1.0)
    travel_time: float        # base travel time in seconds
    lock: threading.Lock      # per-road mutex
```

### Vehicle
```python
@dataclass
class Vehicle:
    id: int
    source: int
    dest: int
    route: List[int]          # list of intersection IDs forming the path
    total_wait: float         # total estimated wait along route
```

### TrafficNetwork
```python
class TrafficNetwork:
    intersections: Dict[int, Intersection]
    roads: Dict[int, Road]
    adjacency: Dict[int, List[int]]   # intersection_id → list of road_ids
    vehicles: List[Vehicle]

    def build_grid(self, side: int): ...   # builds N×N grid network
    def generate_vehicles(self, count: int): ...
```

---

## ALGORITHMS (algorithms.py)

### 1. Signal Optimization — Webster's Formula
**Used by:** `SignalOptimizer` thread worker

Webster's formula computes the optimal cycle length C:
```
C = (1.5 × L + 5) / (1 − Y)
```
Where:
- L = total lost time per cycle (fixed at 4 seconds)
- Y = sum of critical flow ratios = vehicle_count / 100 (capped at 0.9)

Green time per phase:
```
g = C × (vehicle_count / total_demand)
g = clamp(g, 10, 80)  # seconds
```

Each intersection is independently optimizable → **embarrassingly parallel** per intersection.

### 2. Congestion Detection
**Used by:** `CongestionDetector` thread worker

```
congestion_ratio = flow / capacity
bottleneck = congestion_ratio >= 0.8
```

Each road segment is independently computable → **embarrassingly parallel** per road.

### 3. Shortest Path Routing — Dijkstra's Algorithm
**Used by:** `RouteFlowComputer` thread worker

Standard Dijkstra with edge weight:
```
weight(road) = travel_time × (1 + congestion_ratio)
```

Each vehicle's route is independently computable → **embarrassingly parallel** per vehicle.
After routing, road flows are updated atomically using per-road locks.

---

## PARALLEL IMPLEMENTATION (parallel_optimizer.py)

### Thread Workers

#### SignalOptimizer(threading.Thread)
- Input: subset of `Intersection` objects (partitioned by thread index)
- Algorithm: Webster's formula
- Synchronization: `threading.Barrier` — all signal threads must complete before results are written
- Output: writes `optimized_green` and `wait_time` back to each Intersection using per-object lock

#### CongestionDetector(threading.Thread)
- Input: subset of `Road` objects
- Algorithm: flow/capacity ratio
- Synchronization: shared list protected by a global `threading.Lock`
- Output: appends bottleneck records to shared list

#### RouteFlowComputer(threading.Thread)
- Input: subset of `Vehicle` objects
- Algorithm: Dijkstra's shortest path
- Synchronization: per-road `threading.Lock` when updating `road.flow`
- Output: vehicle.route, vehicle.total_wait; updates road flows

### Workload Partitioning
```python
def partition(items: list, num_threads: int) -> List[list]:
    chunk = len(items) // num_threads
    return [items[i*chunk : (i+1)*chunk] for i in range(num_threads)]
    # last thread gets the remainder
```

### Synchronization Primitives Used
| Primitive | Where Used | Purpose |
|---|---|---|
| `threading.Lock` | Per Intersection, per Road | Protect shared mutable state |
| `threading.Lock` | Global results dict/list | Aggregate thread-local results |
| `threading.Barrier` | SignalOptimizer | Phase synchronization |
| `queue.Queue` | RouteFlowComputer stats | Thread-safe statistics aggregation |

### Parallel Run Function
```python
def run_parallel(network: TrafficNetwork, num_threads: int) -> dict:
    results = {}
    bottlenecks = []
    global_lock = threading.Lock()
    barrier = threading.Barrier(num_threads)

    # Phase 1: Signal optimization
    signal_threads = [
        SignalOptimizer(i, partition(intersections, num_threads)[i],
                        results, global_lock, barrier)
        for i in range(num_threads)
    ]
    for t in signal_threads: t.start()
    for t in signal_threads: t.join()

    # Phase 2: Congestion detection
    congestion_threads = [
        CongestionDetector(i, partition(roads, num_threads)[i],
                           bottlenecks, global_lock)
        for i in range(num_threads)
    ]
    for t in congestion_threads: t.start()
    for t in congestion_threads: t.join()

    # Phase 3: Route computation
    stats_q = queue.Queue()
    route_threads = [
        RouteFlowComputer(i, partition(vehicles, num_threads)[i],
                          network, global_lock, stats_q)
        for i in range(num_threads)
    ]
    for t in route_threads: t.start()
    for t in route_threads: t.join()

    return {"signal_results": results, "bottlenecks": bottlenecks, ...}
```

---

## SERIAL IMPLEMENTATION (serial_optimizer.py)

Identical algorithms, but run sequentially in a single thread — no locks, no barriers. Used as the baseline for speedup measurement.

```python
def run_serial(network: TrafficNetwork) -> dict:
    # Phase 1: Signal optimization
    for intr in network.intersections.values():
        optimize_signal(intr)

    # Phase 2: Congestion detection
    for road in network.roads.values():
        detect_congestion(road)

    # Phase 3: Route computation
    for vehicle in network.vehicles:
        compute_route(vehicle, network)
```

---

## BENCHMARKING (benchmark.py)

Run both serial and parallel versions across different configurations and record wall-clock time.

```python
configs = {
    "network_sizes": [16, 25, 36, 49, 64, 81, 100],  # N intersections (NxN grid)
    "thread_counts": [1, 2, 4, 8, 16],
    "vehicle_counts": [50, 100, 200, 500]
}

# For each config:
# 1. Build network
# 2. Run serial → record serial_time
# 3. Run parallel with T threads → record parallel_time
# 4. speedup = serial_time / parallel_time
# 5. efficiency = speedup / T
```

Save results to `benchmark_results.json`.

Expected metrics to report:
- Wall-clock execution time (seconds)
- Speedup S(T) = T_serial / T_parallel
- Efficiency E(T) = S(T) / T
- Amdahl's Law estimate of parallel fraction

---

## VISUALIZATIONS (visualize.py)

Generate these charts using `matplotlib`:

1. **Speedup vs Thread Count** — line plot, one line per network size
2. **Execution Time vs Network Size** — serial vs parallel (4 threads) comparison
3. **Congestion Heatmap** — grid showing congestion ratio per road (color-coded)
4. **Signal Optimization Before/After** — bar chart of green times
5. **Efficiency vs Thread Count** — to show diminishing returns

Save all plots as PNG files in `screenshots/`.

---

## ENTRY POINT (traffic_optimizer.py)

```
python traffic_optimizer.py [OPTIONS]

Options:
  --mode        serial | parallel | benchmark | all   (default: all)
  --threads     number of threads                      (default: 4)
  --grid        grid side length (N produces N×N grid) (default: 8)
  --vehicles    number of vehicles                     (default: 200)
  --verbose     print per-thread timing info

Examples:
  python traffic_optimizer.py --mode all --threads 4 --grid 8
  python traffic_optimizer.py --mode benchmark
  python traffic_optimizer.py --mode parallel --threads 8 --grid 10 --verbose
```

---

## REPORT STRUCTURE (generate_report.js)

Generate using the `docx` npm package. Report must contain:

### Cover Sheet
- Course: CENG 471 Parallel Computing
- Title: Parallel Traffic Flow Optimizer
- Group Member(s): [Name — Student ID]
- Date: April 2026
- University name

### 1. Introduction
- What is traffic flow optimization?
- Why is parallelism beneficial here?
- Scope and goals of the project

### 2. Problem Description
- Description of the traffic network model (grid, intersections, roads, vehicles)
- The three sub-problems: signal timing, congestion detection, route computation
- Serial approach and its limitations

### 3. Parallel Design
- Decomposition strategy (data parallelism)
- Thread worker design (SignalOptimizer, CongestionDetector, RouteFlowComputer)
- Synchronization mechanisms (Lock, Barrier, Queue)
- Workload partitioning

### 4. Algorithms
- Webster's signal optimization formula (with math)
- Congestion detection ratio
- Dijkstra's shortest path with congestion-weighted edges

### 5. Code Listings
- network.py
- algorithms.py
- serial_optimizer.py
- parallel_optimizer.py (key sections)

### 6. Results & Screenshots
- Terminal output screenshots
- Speedup chart
- Efficiency chart
- Congestion heatmap
- Performance table

### 7. Discussion
- Amdahl's Law analysis
- Bottlenecks observed (GIL limitations, lock contention)
- How GIL affects Python threading vs true Pthreads

### 8. Conclusion
- Summary of findings
- What speedup was achieved and why

### 9. References
- Webster (1958) — optimal signal timing
- Dijkstra (1959) — shortest path
- Python threading documentation
- Any textbook references from CENG 471

---

## IMPORTANT NOTES FOR IMPLEMENTATION

### Python GIL Awareness
Python's Global Interpreter Lock (GIL) limits true CPU parallelism for CPU-bound tasks. In this project:
- The GIL means threads may not run truly in parallel for pure computation
- However, the threading module IS a wrapper around Pthreads at the C level
- Speedup can still be demonstrated with I/O simulation (`time.sleep`) and larger datasets
- **In the report, explicitly discuss the GIL** — this shows understanding of Python internals and satisfies the "which group member did which part" section

### Correctness Verification
After parallel run, verify:
- All intersections have `optimized_green` set (not 0.0)
- All roads have `congestion` in [0.0, 1.0]
- All vehicles have a non-empty `route` (or marked as unreachable)
- Total flow on roads is consistent across parallel and serial runs

### Thread Safety Rules
- **Never** read/write an Intersection or Road without acquiring its lock
- **Never** append to shared lists without the global lock
- **Always** join() all threads before reading results
- **Always** use Barrier before aggregating signal results

---

## GRADING ALIGNMENT

| Report Section Required | Where It Appears |
|---|---|
| Cover sheet with name & ID | Cover Sheet section |
| Short project description | Cover Sheet + Introduction |
| Details of the problem | Section 2: Problem Description |
| How it is solved | Section 3: Parallel Design |
| Which member did which part | Section 2 or Introduction |
| Algorithms used | Section 4: Algorithms |
| Code listings | Section 5: Code Listings |
| Screenshots | Section 6: Results & Screenshots |
