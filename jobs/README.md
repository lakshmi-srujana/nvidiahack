# Benchmark worker

Build from the repository root:

```powershell
docker build -f jobs/Dockerfile.bench -t skywarden-bench:local .
```

The worker reads a completed per-attempt JSONL file and writes deterministic
`results.json`, `scoreboard.json`, and `run_manifest.json` artifacts. It does
not call providers or execute plans.

```powershell
docker run --rm `
  -v "${PWD}/backend/bench/cases:/input:ro" `
  -v "${PWD}/results:/output" `
  -e BENCH_INPUT=/input/attempts.jsonl `
  -e BENCH_OUTPUT_DIR=/output/local-run `
  skywarden-bench:local
```

Cloud submission is intentionally deferred until the installed Nebius CLI,
project ID, registry, output storage, quota, and billing account are known.
Record the returned job ID and logs; do not describe a local run as a cloud job.
