// burn_llm_fenced3_addCompute.cpp
// Thread-level pin + ready-go barrier + exit-on-fail
// Adds extra compute (register-only) to let you vary compute intensity.
//
// Usage:
//   ./burn_llm_fenced3_addCompute <threads> <cpu_list> [compute_iters] [steps] [workset_mb]
//
// Examples:
//   ./burn_llm_fenced3_addCompute 1 4
//   ./burn_llm_fenced3_addCompute 2 4,6 0
//   ./burn_llm_fenced3_addCompute 2 4,6 8000
//
// Notes:
// - cpu_list length must be >= threads (e.g., "4,5,6").
// - Prints PIN-OK lines and final Time line (like your fenced3 style).
// - compute_iters is per-step register-only ALU work; it does NOT touch memory.
//
// Build (Termux):
//   clang++ -O3 -std=c++17 -pthread burn_llm_fenced3_addCompute.cpp -o burn_llm_fenced3_addCompute
//
#include <atomic>
#include <cerrno>
#include <chrono>
#include <cstring>
#include <iostream>
#include <pthread.h>
#include <sched.h>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#include <unistd.h>
#include <sys/syscall.h>

static inline pid_t gettid_linux() {
  return (pid_t)syscall(SYS_gettid);
}

static bool pin_this_thread_to_cpu(int cpu) {
  cpu_set_t set;
  CPU_ZERO(&set);
  CPU_SET(cpu, &set);
  // pin calling thread
  int rc = sched_setaffinity(0, sizeof(set), &set);
  return rc == 0;
}

// Simple reusable barrier for N threads + main (optional)
// Here: workers sync among themselves and main uses separate ready flags.
struct SpinBarrier {
  const int n;
  std::atomic<int> arrived;
  std::atomic<int> phase;

  explicit SpinBarrier(int n_) : n(n_), arrived(0), phase(0) {}

  void wait() {
    int ph = phase.load(std::memory_order_relaxed);
    int a = arrived.fetch_add(1, std::memory_order_acq_rel) + 1;
    if (a == n) {
      arrived.store(0, std::memory_order_release);
      phase.fetch_add(1, std::memory_order_acq_rel);
    } else {
      while (phase.load(std::memory_order_acquire) == ph) {
        // spin
#if defined(__aarch64__) || defined(__arm__)
        asm volatile("yield" ::: "memory");
#else
        std::this_thread::yield();
#endif
      }
    }
  }
};

// Parse "4,5,6" -> {4,5,6}
static std::vector<int> parse_cpu_list(const std::string& s) {
  std::vector<int> cpus;
  int cur = 0;
  bool in_num = false;
  for (size_t i = 0; i <= s.size(); ++i) {
    char c = (i < s.size() ? s[i] : ',');
    if (c >= '0' && c <= '9') {
      cur = cur * 10 + (c - '0');
      in_num = true;
    } else if (c == ',' || c == ' ' || c == '\t') {
      if (in_num) {
        cpus.push_back(cur);
        cur = 0;
        in_num = false;
      }
    } else {
      throw std::runtime_error("Invalid cpu_list char: " + std::string(1, c));
    }
  }
  if (cpus.empty()) throw std::runtime_error("cpu_list is empty");
  return cpus;
}

// Extra compute: register-only ALU ops (no memory traffic)
static inline void extra_compute(int iters) {
  // volatile to prevent the compiler from optimizing it away
  volatile uint64_t x = 0x123456789abcdefULL;
  for (int i = 0; i < iters; ++i) {
    // Mix of mul/add/xor/shift (fast ALU)
    x = x * 1664525u + 1013904223u;
    x ^= (x >> 13);
    x ^= (x << 7);
    x += 0x9e3779b97f4a7c15ULL;
  }
}

// Memory workset touch: stride through buffer to generate cache misses
static inline uint64_t touch_workset(uint8_t* buf, size_t bytes) {
  // 64B stride approximates cacheline stepping
  constexpr size_t STRIDE = 64;
  uint64_t acc = 0;
  for (size_t i = 0; i < bytes; i += STRIDE) {
    acc += buf[i];
    buf[i] = static_cast<uint8_t>(buf[i] + 1);
  }
  return acc;
}

struct WorkerArgs {
  int worker_idx;
  int cpu;
  int steps;
  int compute_iters;
  uint8_t* buf;
  size_t bytes;
  SpinBarrier* barrier;
  std::atomic<int>* ready_count;
  std::atomic<int>* start_flag;
  std::atomic<uint64_t>* sink;
};

static void* worker_main(void* p) {
  auto* a = reinterpret_cast<WorkerArgs*>(p);

  // Pin
  if (!pin_this_thread_to_cpu(a->cpu)) {
    std::cerr << "[PIN-FAIL] tid=" << gettid_linux()
              << " cpu=" << a->cpu
              << " errno=" << errno << " (" << strerror(errno) << ")\n";
    // Exit-on-fail: kill process
    _exit(2);
  }
  std::cerr << "[PIN-OK] tid=" << gettid_linux() << " cpu=" << a->cpu << "\n";

  // Signal ready
  a->ready_count->fetch_add(1, std::memory_order_release);

  // Wait for main to release start
  while (a->start_flag->load(std::memory_order_acquire) == 0) {
#if defined(__aarch64__) || defined(__arm__)
    asm volatile("yield" ::: "memory");
#else
    std::this_thread::yield();
#endif
  }

  // Align start across workers
  a->barrier->wait();

  uint64_t local = 0;
  for (int s = 0; s < a->steps; ++s) {
    // Memory part
    local += touch_workset(a->buf, a->bytes);
    // Compute part (this is the "addCompute" knob)
    if (a->compute_iters > 0) extra_compute(a->compute_iters);
  }

  a->sink->fetch_add(local, std::memory_order_relaxed);
  return nullptr;
}

int main(int argc, char** argv) {
  try {
    if (argc < 3) {
      std::cerr << "Usage: " << argv[0]
                << " <threads> <cpu_list> [compute_iters] [steps] [workset_mb]\n";
      return 1;
    }

    int threads = std::stoi(argv[1]);
    std::string cpu_list_str = argv[2];

    int compute_iters = 0;    // default: no extra compute
    int steps = 200;          // default
    int workset_mb = 64;      // default

    if (argc >= 4) compute_iters = std::stoi(argv[3]);
    if (argc >= 5) steps = std::stoi(argv[4]);
    if (argc >= 6) workset_mb = std::stoi(argv[5]);

    if (threads <= 0) throw std::runtime_error("threads must be > 0");
    if (steps <= 0) throw std::runtime_error("steps must be > 0");
    if (workset_mb <= 0) throw std::runtime_error("workset_mb must be > 0");

    auto cpus = parse_cpu_list(cpu_list_str);
    if ((int)cpus.size() < threads) {
      throw std::runtime_error("cpu_list has fewer entries than threads");
    }

    std::cerr << "[FENCED3_ADDCOMPUTE_BUILD] pin+readygo+exit_on_fail v1"
              << " compute_iters=" << compute_iters
              << " steps=" << steps
              << " workset_mb=" << workset_mb
              << "\n";

    // Allocate per-thread workset (avoid false sharing & contention from sharing same buffer)
    // If you want stronger contention, you can intentionally share buffers instead.
    size_t bytes = (size_t)workset_mb * 1024ull * 1024ull;
    std::vector<std::vector<uint8_t>> bufs(threads);
    for (int t = 0; t < threads; ++t) {
      bufs[t].resize(bytes);
      // Touch once to fault in pages
      for (size_t i = 0; i < bytes; i += 4096) bufs[t][i] = (uint8_t)(t + 1);
    }

    SpinBarrier barrier(threads);
    std::atomic<int> ready_count{0};
    std::atomic<int> start_flag{0};
    std::atomic<uint64_t> sink{0};

    std::vector<pthread_t> ths(threads);
    std::vector<WorkerArgs> args(threads);

    for (int t = 0; t < threads; ++t) {
      args[t] = WorkerArgs{
        .worker_idx = t,
        .cpu = cpus[t],
        .steps = steps,
        .compute_iters = compute_iters,
        .buf = bufs[t].data(),
        .bytes = bytes,
        .barrier = &barrier,
        .ready_count = &ready_count,
        .start_flag = &start_flag,
        .sink = &sink
      };
      int rc = pthread_create(&ths[t], nullptr, worker_main, &args[t]);
      if (rc != 0) throw std::runtime_error("pthread_create failed");
    }

    // Wait all pinned & ready
    while (ready_count.load(std::memory_order_acquire) < threads) {
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }

    // Release start
    auto t0 = std::chrono::steady_clock::now();
    start_flag.store(1, std::memory_order_release);

    for (int t = 0; t < threads; ++t) {
      pthread_join(ths[t], nullptr);
    }
    auto t1 = std::chrono::steady_clock::now();

    double sec = std::chrono::duration<double>(t1 - t0).count();
    // Keep sink used
    if (sink.load(std::memory_order_relaxed) == 0xdeadbeefULL) {
      std::cerr << "sink hit\n";
    }

    std::cout << "Threads: " << threads << "  Time: " << sec << " seconds\n";
    return 0;
  } catch (const std::exception& e) {
    std::cerr << "Error: " << e.what() << "\n";
    return 1;
  }
}
