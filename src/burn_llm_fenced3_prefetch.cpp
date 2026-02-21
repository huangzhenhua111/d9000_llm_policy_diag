#include <iostream>
#include <vector>
#include <thread>
#include <chrono>
#include <cstdlib>
#include <atomic>
#include <string>
#include <sstream>
#include <cerrno>
#include <cstring>
#include <sched.h>
#include <unistd.h>
#include <sys/syscall.h>
#include <sys/types.h>

using namespace std;

#ifndef PREFETCH_HINT
#define PREFETCH_HINT 3
#endif

#ifndef WORKSET_MB
#define WORKSET_MB 64
#endif

#ifndef PREFETCH_CL
#define PREFETCH_CL 0   // prefetch distance in cache-lines (64B)
#endif

constexpr size_t CACHELINE_FLOATS = 16; // 64B / sizeof(float)

constexpr int STEPS = 200;

// --- simple spin barrier for token boundary ---
struct SimpleBarrier {
    atomic<int> count;
    atomic<int> sense;
    int total;

    SimpleBarrier(int n) : count(0), sense(0), total(n) {}

    void wait() {
        int local = sense.load(memory_order_relaxed);
        if (count.fetch_add(1, memory_order_acq_rel) == total - 1) {
            count.store(0, memory_order_release);
            sense.store(1 - local, memory_order_release);
        } else {
            while (sense.load(memory_order_acquire) == local) {}
        }
    }
};

static vector<int> parse_cpu_list(const string& s) {
    vector<int> cpus;
    string token;
    stringstream ss(s);
    while (getline(ss, token, ',')) {
        if (token.empty()) continue;
        // trim spaces
        while (!token.empty() && isspace(token.front())) token.erase(token.begin());
        while (!token.empty() && isspace(token.back())) token.pop_back();
        if (token.empty()) continue;
        cpus.push_back(stoi(token));
    }
    return cpus;
}

static pid_t gettid_linux() { return (pid_t)syscall(SYS_gettid); }

static void pin_this_thread_to_cpu(int cpu) {
    cpu_set_t set;
    CPU_ZERO(&set);
    CPU_SET(cpu, &set);

    int rc = sched_setaffinity(0, sizeof(set), &set);
    if (rc != 0) {
        int e = errno;
        cerr << "[PIN-FAIL] tid=" << gettid_linux()
             << " cpu=" << cpu
             << " errno=" << e
             << " (" << strerror(e) << ")\n";
        _exit(100 + (e % 100));
    } else {
        cerr << "[PIN-OK] tid=" << gettid_linux() << " cpu=" << cpu << "\n";
    }
}

int main(int argc, char** argv) {
cerr << "[FENCED3_BUILD] pin+readygo+exit_on_fail v1\n";
    if (argc < 3) {
        cerr << "Usage: " << argv[0] << " <threads> <cpu_list_csv>\n";
        return 2;
    }

    int threads = atoi(argv[1]);
    string cpu_csv = argv[2];

    vector<int> cpu_targets = parse_cpu_list(cpu_csv);
    if ((int)cpu_targets.size() != threads) {
        cerr << "[ERR] cpu_list count (" << cpu_targets.size()
             << ") != threads (" << threads << "). "
             << "Example: threads=2 cpu_list=4,1\n";
        return 3;
    }

    size_t elements = (WORKSET_MB * 1024ULL * 1024ULL) / sizeof(float);
    vector<float> kv(elements, 1.0f);

    SimpleBarrier token_barrier(threads);

    // --- make pinning deterministic ---
    atomic<int> ready{0};
    atomic<int> go{0};

    vector<thread> ts;
    ts.reserve(threads);

    for (int t = 0; t < threads; ++t) {
        ts.emplace_back([&, t]() {
            // pin immediately
            pin_this_thread_to_cpu(cpu_targets[t]);

            // mark ready, then wait "go"
            ready.fetch_add(1, memory_order_release);
            while (go.load(memory_order_acquire) == 0) {}

            // work partition
            size_t chunk = elements / threads;
            size_t begin = (size_t)t * chunk;
            size_t end = (t == threads - 1) ? elements : (begin + chunk);

            for (int step = 0; step < STEPS; ++step) {
                for (size_t i = begin; i < end; ++i) {
                  #if PREFETCH_CL > 0
  // one prefetch per cache line to avoid instruction/traffic explosion
  if (((i - begin) & (CACHELINE_FLOATS - 1)) == 0) {
    size_t pf_i = i + (size_t)PREFETCH_CL * CACHELINE_FLOATS;
    if (pf_i < end) __builtin_prefetch(&kv[pf_i], 0, PREFETCH_HINT);
  }
#endif
                  kv[i] = kv[i] * 1.000001f + 0.0000001f;
                }
                atomic_thread_fence(memory_order_seq_cst);
                token_barrier.wait();
            }
        });
    }

    // wait until all workers pinned
    while (ready.load(memory_order_acquire) != threads) {}

    // start timing only after pinning is done
    auto start = chrono::high_resolution_clock::now();
    go.store(1, memory_order_release);

    for (auto& th : ts) th.join();
    auto end = chrono::high_resolution_clock::now();

    double sec = chrono::duration<double>(end - start).count();
    cout << "Threads: " << threads << "  Time: " << sec << " seconds\n";
    return 0;
}
