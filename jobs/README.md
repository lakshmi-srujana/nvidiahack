# Benchmark worker

Build from the repository root:

```powershell
docker build -f jobs/Dockerfile.bench -t skywarden-bench:local .
```

The worker can either aggregate a completed per-attempt JSONL file or execute a
bounded benchmark shard through an injected `module:factory` adapter. It writes
deterministic JSONL, CSV, results, scoreboard, and manifest artifacts. RAW plans
are verifier-scored only and are never sent to an executor.

```powershell
docker run --rm `
  -v "${PWD}/backend/bench/cases:/input:ro" `
  -v "${PWD}/results:/output" `
  -e BENCH_INPUT=/input/attempts.jsonl `
  -e BENCH_OUTPUT_DIR=/output/local-run `
  skywarden-bench:local
```

Pipeline-only smoke with the explicitly fake adapter:

```powershell
docker run --rm `
  -v "${PWD}/backend/bench/cases:/input:ro" `
  -v "${PWD}/results:/output" `
  skywarden-bench:local `
  --suite /input/fixed-v1.jsonl `
  --adapter bench.fixture_adapter:create `
  --output-dir /output/fixture-smoke `
  --run-id fixture-smoke `
  --max-cases 3 --concurrency 2 --allow-mock
```

`--allow-mock` is deliberately required for the fixture adapter, and its
manifest is marked `DO_NOT_PUBLISH_AS_REAL_RESULTS`. A real benchmark adapter
must generate one initial candidate per case, call the external verifier, and
perform model-backed repairs while exposing provider usage metadata.

Cloud submission is intentionally deferred until the installed Nebius CLI,
project ID, registry, output storage, quota, and billing account are known.
Record the returned job ID and logs; do not describe a local run as a cloud job.
