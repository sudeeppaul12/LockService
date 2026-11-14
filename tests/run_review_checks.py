"""Save repeatable review evidence; timings are local sequential microbenchmarks."""
import io
import json
import platform
import sqlite3
import statistics
import sys
import time
import unittest
from datetime import datetime
from importlib.metadata import version
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_backend import BackendTests

out = Path(__file__).resolve().parents[1] / 'docs' / 'testing'
out.mkdir(parents=True, exist_ok=True)
stream = io.StringIO()
suite = unittest.defaultTestLoader.loadTestsFromTestCase(BackendTests)
start = time.perf_counter()
result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
elapsed = time.perf_counter() - start
(out / 'backend-test-results.txt').write_text(stream.getvalue(), encoding='utf-8')

BackendTests.setUpClass()
case = BackendTests('test_rendered_pages')
try:
    case.setUp()
    case.login_as()
    samples = []
    statuses = {}
    for _ in range(100):
        start = time.perf_counter()
        response = case.client.get('/customer')
        samples.append((time.perf_counter() - start) * 1000)
        statuses[str(response.status_code)] = statuses.get(str(response.status_code), 0) + 1
    data = dict(recorded_local=datetime.now().isoformat(), python=sys.version,
                platform=platform.platform(), sqlite=sqlite3.sqlite_version,
                packages={p: version(p) for p in ['Flask', 'Werkzeug']},
                tests_run=result.testsRun, expected_failures=len(result.expectedFailures),
                failures=len(result.failures), errors=len(result.errors), test_seconds=elapsed,
                benchmark=dict(requests=100, dataset='3 users, 1 vehicle, 1 appointment',
                               route='/customer', concurrency=1, transport='Flask test client; no network',
                               status_counts=statuses, mean_ms=statistics.mean(samples),
                               p95_ms=sorted(samples)[94], max_ms=max(samples)))
    (out / 'environment-and-performance.json').write_text(json.dumps(data, indent=2), encoding='utf-8')
finally:
    case.tearDown()
    BackendTests.tearDownClass()
print(stream.getvalue())
print(json.dumps(data, indent=2))
sys.exit(0 if result.wasSuccessful() else 1)
