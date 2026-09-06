#!/usr/bin/env python3
"""Authenticated read-load probe; OCR capacity requires separate representative document trials.

OCR_LOAD_TOKEN is never logged. Run only against an authorized test deployment.
Example: python scripts/load_api.py https://ocr.example.org --users 50 --requests 20
"""
import argparse
import concurrent.futures
import json
import os
import statistics
import time
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('origin')
    parser.add_argument('--users', type=int, default=50)
    parser.add_argument('--requests', type=int, default=20, help='Requests per simulated user')
    args = parser.parse_args()
    if args.users < 1 or args.requests < 1:
        parser.error('users and requests must be positive')
    token = os.environ.get('OCR_LOAD_TOKEN')
    if not token:
        parser.error('OCR_LOAD_TOKEN must hold a scoped test API key')
    if not args.origin.startswith(('https://', 'http://localhost:', 'http://127.0.0.1:')):
        parser.error('Use HTTPS except for local testing')
    url = args.origin.rstrip('/') + '/api/v1/jobs'

    def simulate(_):
        results = []
        for _ in range(args.requests):
            start = time.monotonic()
            request = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token})
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    response.read()
                    ok = response.status == 200
            except (urllib.error.URLError, TimeoutError):
                ok = False
            results.append((time.monotonic() - start, ok))
        return results

    start = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.users) as executor:
        results = [item for batch in executor.map(simulate, range(args.users)) for item in batch]
    durations = sorted(value for value, _ in results)
    errors = sum(not ok for _, ok in results)
    print(json.dumps({'users': args.users, 'requests': len(results), 'errors': errors,
                      'elapsed_seconds': round(time.monotonic() - start, 3),
                      'latency_median_seconds': round(statistics.median(durations), 3),
                      'latency_p95_seconds': round(durations[min(len(durations)-1, int(len(durations)*0.95))], 3)}, indent=2))
    raise SystemExit(1 if errors else 0)


if __name__ == '__main__':
    main()
