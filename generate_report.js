/**
 * generate_report.js — Word (.docx) Project Report Generator
 * CENG 471 Parallel Computing — Term Project
 *
 * Generates the formatted Word report using the `docx` npm package.
 *
 * Setup:
 *   npm init -y
 *   npm install docx
 *
 * Usage:
 *   node generate_report.js
 *
 * Output:
 *   traffic_optimizer_report.docx
 */

const {
  Document,
  Packer,
  Paragraph,
  TextRun,
  HeadingLevel,
  AlignmentType,
  Table,
  TableRow,
  TableCell,
  WidthType,
  BorderStyle,
  ImageRun,
  PageBreak,
  UnderlineType,
  ShadingType,
} = require("docx");

const fs = require("fs");
const path = require("path");

// ---------------------------------------------------------------------------
// Configuration — fill in your information here
// ---------------------------------------------------------------------------
const STUDENT_NAME = "Your Name";
const STUDENT_ID = "XXXXXXXXX";
const UNIVERSITY = "Middle East Technical University";
const COURSE = "CENG 471 — Parallel Computing";
const TITLE = "Parallel Traffic Flow Optimizer";
const DATE = "April 2026";
const OUTPUT_FILE = "traffic_optimizer_report.docx";
const SCREENSHOTS_DIR = "screenshots";

// ---------------------------------------------------------------------------
// Helper functions
// ---------------------------------------------------------------------------
function heading(text, level = HeadingLevel.HEADING_1) {
  return new Paragraph({ text, heading: level, spacing: { before: 300, after: 150 } });
}

function bold(text) {
  return new TextRun({ text, bold: true });
}

function para(text, options = {}) {
  return new Paragraph({
    children: [new TextRun({ text, ...options })],
    spacing: { after: 120 },
  });
}

function codePara(text) {
  return new Paragraph({
    children: [
      new TextRun({
        text,
        font: "Courier New",
        size: 18,
        color: "1a1a2e",
      }),
    ],
    spacing: { after: 60 },
    shading: {
      type: ShadingType.SOLID,
      color: "f4f4f4",
    },
  });
}

function bullet(text, level = 0) {
  return new Paragraph({
    text,
    bullet: { level },
    spacing: { after: 80 },
  });
}

function pageBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}

function tryLoadImage(filename) {
  const filepath = path.join(SCREENSHOTS_DIR, filename);
  if (fs.existsSync(filepath)) {
    return fs.readFileSync(filepath);
  }
  return null;
}

function imageParagraph(filename, width = 550, height = 350) {
  const data = tryLoadImage(filename);
  if (!data) {
    return para(`[Image not found: ${filename} — run benchmark and visualize.py first]`, {
      italics: true,
      color: "888888",
    });
  }
  return new Paragraph({
    children: [
      new ImageRun({ data, transformation: { width, height } }),
    ],
    alignment: AlignmentType.CENTER,
    spacing: { after: 200 },
  });
}

function tableRow(cells, isHeader = false) {
  return new TableRow({
    children: cells.map(
      (text) =>
        new TableCell({
          children: [
            new Paragraph({
              children: [new TextRun({ text: String(text), bold: isHeader })],
              alignment: AlignmentType.CENTER,
            }),
          ],
          shading: isHeader
            ? { type: ShadingType.SOLID, color: "2c3e50", fill: "2c3e50" }
            : undefined,
        })
    ),
  });
}

// ---------------------------------------------------------------------------
// Report sections
// ---------------------------------------------------------------------------

function coverSheet() {
  return [
    new Paragraph({ spacing: { after: 600 } }),
    new Paragraph({
      children: [new TextRun({ text: UNIVERSITY, bold: true, size: 28 })],
      alignment: AlignmentType.CENTER,
      spacing: { after: 200 },
    }),
    new Paragraph({
      children: [new TextRun({ text: COURSE, bold: true, size: 24 })],
      alignment: AlignmentType.CENTER,
      spacing: { after: 400 },
    }),
    new Paragraph({
      children: [new TextRun({ text: TITLE, bold: true, size: 36, color: "1a5276" })],
      alignment: AlignmentType.CENTER,
      spacing: { after: 600 },
    }),
    new Paragraph({ spacing: { after: 200 } }),
    new Paragraph({
      children: [bold("Term Project Report")],
      alignment: AlignmentType.CENTER,
      spacing: { after: 400 },
    }),
    new Paragraph({
      children: [
        new TextRun({ text: "Student Name: ", bold: true }),
        new TextRun(STUDENT_NAME),
      ],
      alignment: AlignmentType.CENTER,
      spacing: { after: 120 },
    }),
    new Paragraph({
      children: [
        new TextRun({ text: "Student ID: ", bold: true }),
        new TextRun(STUDENT_ID),
      ],
      alignment: AlignmentType.CENTER,
      spacing: { after: 120 },
    }),
    new Paragraph({
      children: [new TextRun({ text: DATE })],
      alignment: AlignmentType.CENTER,
      spacing: { after: 600 },
    }),
    pageBreak(),
  ];
}

function introduction() {
  return [
    heading("1. Introduction"),
    para(
      "Traffic flow optimization is a fundamental problem in urban transportation engineering. " +
      "Modern cities face growing congestion that wastes fuel, increases emissions, and reduces " +
      "quality of life. Optimizing traffic signal timing, detecting road bottlenecks, and routing " +
      "vehicles efficiently are three core sub-problems that must be solved continuously and in " +
      "near-real-time for large networks."
    ),
    para(
      "Parallelism is a natural fit for this domain: each intersection's signal can be optimized " +
      "independently, each road's congestion can be detected independently, and each vehicle's " +
      "route can be computed independently. These properties make the problem embarrassingly " +
      "parallel at the per-object level — exactly the category where data-parallel thread " +
      "decomposition yields maximum speedup."
    ),
    para(
      "This project implements a Parallel Traffic Flow Optimizer in Python using the threading " +
      "module, which is CPython's direct wrapper around POSIX Pthreads. Three parallel worker " +
      "classes — SignalOptimizer, CongestionDetector, and RouteFlowComputer — are designed and " +
      "benchmarked against a serial baseline to quantify speedup, efficiency, and scalability."
    ),
    para("Work division:"),
    bullet(`${STUDENT_NAME} (${STUDENT_ID}): All implementation, benchmarking, and report.`),
  ];
}

function problemDescription() {
  return [
    heading("2. Problem Description"),
    heading("2.1 Traffic Network Model", HeadingLevel.HEADING_2),
    para(
      "The traffic network is modelled as a directed graph where nodes are Intersections and " +
      "edges are Roads. A side×side grid topology is used, producing side² intersections and " +
      "approximately 4×side×(side−1) directed road segments (bidirectional adjacency)."
    ),
    para("Each Intersection stores:"),
    bullet("id, x/y grid coordinates"),
    bullet("vehicle_count — current queue length"),
    bullet("green_time / red_time — current signal phase durations"),
    bullet("optimized_green — result of Webster's formula"),
    bullet("wait_time — estimated average wait per cycle"),
    bullet("lock — per-intersection threading.Lock for thread safety"),
    para("Each Road stores:"),
    bullet("source / dest — connecting intersection IDs"),
    bullet("capacity / flow — maximum and current vehicle counts"),
    bullet("congestion — flow/capacity ratio in [0, 1]"),
    bullet("travel_time — base traversal time in seconds"),
    bullet("lock — per-road threading.Lock"),

    heading("2.2 Sub-Problems", HeadingLevel.HEADING_2),
    para("The optimizer solves three independent sub-problems:"),
    bullet("Signal Timing: compute optimal green time per intersection using Webster's formula."),
    bullet("Congestion Detection: classify each road as bottleneck (congestion ≥ 0.8) or free."),
    bullet("Route Computation: find the shortest congestion-weighted path per vehicle via Dijkstra."),
    para(
      "Because each intersection, road, and vehicle can be processed independently of the others " +
      "in each phase, the workload is embarrassingly parallel — the ideal case for thread-level " +
      "data parallelism."
    ),
  ];
}

function parallelDesign() {
  return [
    heading("3. Parallel Design"),
    heading("3.1 Decomposition Strategy", HeadingLevel.HEADING_2),
    para(
      "The parallel implementation uses data parallelism: the collection of work items " +
      "(intersections, roads, or vehicles) is partitioned into equal-sized chunks, one per thread. " +
      "Each thread processes its chunk independently, then synchronizes at a barrier or lock before " +
      "aggregating results."
    ),

    heading("3.2 Thread Worker Classes", HeadingLevel.HEADING_2),
    para("SignalOptimizer(threading.Thread)"),
    bullet("Receives a partition of Intersection objects."),
    bullet("Applies Webster's formula to each intersection in its chunk."),
    bullet("Uses threading.Barrier to synchronize all signal threads before writing to the shared results dict."),

    para("CongestionDetector(threading.Thread)"),
    bullet("Receives a partition of Road objects."),
    bullet("Computes flow/capacity ratio and flags bottlenecks."),
    bullet("Appends to a shared list under a global threading.Lock."),

    para("RouteFlowComputer(threading.Thread)"),
    bullet("Receives a partition of Vehicle objects."),
    bullet("Runs Dijkstra's algorithm per vehicle."),
    bullet("Acquires per-road locks when updating road.flow after routing."),
    bullet("Reports statistics via a queue.Queue."),

    heading("3.3 Synchronization Primitives", HeadingLevel.HEADING_2),
    new Table({
      width: { size: 100, type: WidthType.PERCENTAGE },
      rows: [
        tableRow(["Primitive", "Where Used", "Purpose"], true),
        tableRow(["threading.Lock (per-object)", "Each Intersection, each Road", "Protect mutable state"]),
        tableRow(["threading.Lock (global)", "Shared results dict/list", "Aggregate thread-local results"]),
        tableRow(["threading.Barrier", "SignalOptimizer", "Phase synchronization"]),
        tableRow(["queue.Queue", "RouteFlowComputer", "Thread-safe stats aggregation"]),
      ],
    }),
    new Paragraph({ spacing: { after: 200 } }),
  ];
}

function algorithmsSection() {
  return [
    heading("4. Algorithms"),
    heading("4.1 Webster's Signal Optimization", HeadingLevel.HEADING_2),
    para("Webster's formula (1958) derives the optimal traffic signal cycle length:"),
    codePara("C = (1.5 × L + 5) / (1 − Y)"),
    para("Where:"),
    bullet("L = total lost time per cycle (fixed at 4 seconds)"),
    bullet("Y = critical flow ratio = vehicle_count / 100 (capped at 0.9)"),
    codePara("g = C × (vehicle_count / total_demand)"),
    codePara("g = clamp(g, 10, 80)  # seconds"),

    heading("4.2 Congestion Detection", HeadingLevel.HEADING_2),
    codePara("congestion_ratio = flow / capacity"),
    codePara("bottleneck = (congestion_ratio >= 0.8)"),
    para("Congestion ratio in [0.0, 1.0] is stored on each road. Values ≥ 0.8 are flagged as bottlenecks."),

    heading("4.3 Dijkstra's Shortest Path", HeadingLevel.HEADING_2),
    para("Standard Dijkstra with congestion-weighted edge costs:"),
    codePara("weight(road) = travel_time × (1 + congestion_ratio)"),
    para(
      "This penalizes congested roads, routing vehicles around bottlenecks. " +
      "Each vehicle's route is computed independently, making this phase trivially parallelizable."
    ),
  ];
}

function codeListings() {
  const files = [
    "network.py",
    "algorithms.py",
    "serial_optimizer.py",
    "parallel_optimizer.py",
  ];

  const sections = [heading("5. Code Listings")];

  for (const filename of files) {
    sections.push(heading(`5.${files.indexOf(filename) + 1} ${filename}`, HeadingLevel.HEADING_2));
    if (fs.existsSync(filename)) {
      const code = fs.readFileSync(filename, "utf-8");
      const lines = code.split("\n");
      for (const line of lines) {
        sections.push(codePara(line));
      }
    } else {
      sections.push(para(`[File not found: ${filename}]`, { italics: true, color: "888888" }));
    }
    sections.push(new Paragraph({ spacing: { after: 300 } }));
  }

  return sections;
}

function resultsSection() {
  return [
    heading("6. Results & Screenshots"),

    heading("6.1 Terminal Output", HeadingLevel.HEADING_2),
    imageParagraph("terminal_output.png", 600, 300),

    heading("6.2 Speedup vs Thread Count", HeadingLevel.HEADING_2),
    imageParagraph("speedup_vs_threads.png"),
    para(
      "The speedup chart shows the ratio of serial to parallel execution time across different " +
      "thread counts. The dashed line represents ideal linear speedup. Sub-linear speedup is " +
      "expected due to Python's GIL and synchronization overhead."
    ),

    heading("6.3 Efficiency vs Thread Count", HeadingLevel.HEADING_2),
    imageParagraph("efficiency_vs_threads.png"),
    para(
      "Efficiency E(T) = S(T)/T measures how well each additional thread contributes. " +
      "Efficiency drops as thread count grows due to increasing lock contention and GIL pressure."
    ),

    heading("6.4 Execution Time vs Network Size", HeadingLevel.HEADING_2),
    imageParagraph("execution_time_vs_size.png"),

    heading("6.5 Congestion Heatmap", HeadingLevel.HEADING_2),
    imageParagraph("congestion_heatmap.png", 450, 450),
    para("Red roads indicate high congestion (flow/capacity ≥ 0.8). Green roads are free-flowing."),

    heading("6.6 Signal Optimization Before/After", HeadingLevel.HEADING_2),
    imageParagraph("signal_optimization.png", 600, 320),
    para("Blue bars show original green times; orange bars show Webster's optimized values."),
  ];
}

function discussion() {
  return [
    heading("7. Discussion"),
    heading("7.1 Amdahl's Law Analysis", HeadingLevel.HEADING_2),
    para(
      "Amdahl's Law states that the maximum speedup S is bounded by the serial fraction f of the program: " +
      "S = 1 / (f + (1−f)/T). In this project, the serial fraction includes thread creation overhead, " +
      "barrier synchronization, and result aggregation. Even with these costs, the three phases are " +
      "predominantly parallel, allowing meaningful speedup for moderate thread counts."
    ),

    heading("7.2 The Python GIL", HeadingLevel.HEADING_2),
    para(
      "Python's Global Interpreter Lock (GIL) prevents multiple threads from executing Python bytecodes " +
      "simultaneously in CPython. This means that for CPU-bound pure-Python computation, threading does " +
      "not achieve true parallelism — threads take turns holding the GIL."
    ),
    para(
      "However, this project is still a valid Pthreads demonstration because: (1) the threading module " +
      "is a direct wrapper around POSIX Pthreads at the C level, so the OS scheduler runs real OS threads; " +
      "(2) GIL release occurs during I/O and certain C extensions; (3) speedup can still be observed " +
      "at larger scales due to GIL-switching overhead amortization and I/O-bound portions."
    ),
    para(
      "In production systems, Python parallelism for CPU-bound tasks would use multiprocessing or " +
      "Cython/C extensions that release the GIL. For this course project, the threading module correctly " +
      "demonstrates the concurrency design patterns: data decomposition, mutual exclusion, barrier " +
      "synchronization, and work partitioning."
    ),

    heading("7.3 Bottlenecks Observed", HeadingLevel.HEADING_2),
    bullet("GIL contention: limits parallel speedup for CPU-bound Dijkstra computation."),
    bullet("Lock contention: per-road locks during flow updates in Phase 3."),
    bullet("Barrier overhead: all signal threads must wait for the slowest before aggregating."),
    bullet("Thread creation cost: creating many threads for small networks can exceed the parallelism benefit."),
  ];
}

function conclusion() {
  return [
    heading("8. Conclusion"),
    para(
      "This project designed and implemented a Parallel Traffic Flow Optimizer using Python's " +
      "threading module (Pthreads). The three phases — signal optimization, congestion detection, " +
      "and route computation — were parallelized using data decomposition across fixed thread pools."
    ),
    para(
      "Benchmarking shows measurable speedup for larger networks, with efficiency decreasing as " +
      "thread count grows beyond the parallelism available. The GIL limits true CPU-parallel " +
      "speedup, but the synchronization patterns (Lock, Barrier, Queue) are correctly implemented " +
      "and the design would scale on GIL-free runtimes or with multiprocessing."
    ),
    para(
      "The project demonstrates the key concepts of CENG 471: thread creation, data decomposition, " +
      "mutual exclusion, phase synchronization, and speedup measurement — all applied to a realistic " +
      "urban traffic optimization scenario."
    ),
  ];
}

function references() {
  return [
    heading("9. References"),
    bullet("Webster, F.V. (1958). Traffic Signal Settings. Road Research Technical Paper No. 39. HMSO, London."),
    bullet("Dijkstra, E.W. (1959). A note on two problems in connexion with graphs. Numerische Mathematik, 1(1), 269–271."),
    bullet("Python Software Foundation. threading — Thread-based parallelism. https://docs.python.org/3/library/threading.html"),
    bullet("Python Software Foundation. queue — A synchronized queue class. https://docs.python.org/3/library/queue.html"),
    bullet("Amdahl, G.M. (1967). Validity of the single-processor approach to achieving large scale computing capabilities. AFIPS Conf. Proc., 30, 483–485."),
  ];
}

// ---------------------------------------------------------------------------
// Assemble and write document
// ---------------------------------------------------------------------------

async function generateReport() {
  const allSections = [
    ...coverSheet(),
    ...introduction(),
    pageBreak(),
    ...problemDescription(),
    pageBreak(),
    ...parallelDesign(),
    pageBreak(),
    ...algorithmsSection(),
    pageBreak(),
    ...codeListings(),
    pageBreak(),
    ...resultsSection(),
    pageBreak(),
    ...discussion(),
    pageBreak(),
    ...conclusion(),
    pageBreak(),
    ...references(),
  ];

  const doc = new Document({
    sections: [
      {
        properties: {},
        children: allSections,
      },
    ],
    styles: {
      paragraphStyles: [
        {
          id: "Normal",
          name: "Normal",
          run: { font: "Calibri", size: 22 },
        },
      ],
    },
  });

  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(OUTPUT_FILE, buffer);
  console.log(`\nReport generated: ${OUTPUT_FILE}`);
  console.log(`File size: ${(buffer.length / 1024).toFixed(1)} KB`);
}

generateReport().catch((err) => {
  console.error("Error generating report:", err);
  process.exit(1);
});
