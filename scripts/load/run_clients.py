"""Paced localhost capacity test; no production targets, login storms or external messages."""
import argparse
import asyncio
import collections
import json
import math
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import aiohttp


def local_origin(value):
    endpoint = urlsplit(value)
    if (endpoint.scheme != 'http' or endpoint.hostname not in {'127.0.0.1', 'localhost', '::1'}
            or endpoint.username or endpoint.password or endpoint.path not in {'', '/'}
            or endpoint.query or endpoint.fragment):
        raise argparse.ArgumentTypeError('This baseline test only targets a localhost HTTP origin')
    return value.rstrip('/')


async def run(args):
    users = json.loads(args.clients.read_text())[:args.users]
    if len(users) != args.users or len({user['id'] for user in users}) != args.users:
        raise ValueError('Provide one distinct synthetic client per simulated user')
    statuses = collections.Counter()
    latencies = []
    plateau = []
    completed = collections.Counter()
    paths = ['/api/v1/auth/me', '/api/v1/habits', '/api/v1/notifications', '/api/v1/programs/assignments']
    start = time.monotonic()
    deadline = start + args.ramp + args.hold
    async with aiohttp.ClientSession(base_url=args.origin, timeout=aiohttp.ClientTimeout(total=10),
                                     connector=aiohttp.TCPConnector(limit=args.users), trust_env=False) as client:
        async def person(index, user):
            await asyncio.sleep(args.ramp * index / args.users)
            iteration = index
            while time.monotonic() < deadline:
                began = time.monotonic()
                try:
                    headers = {'Authorization': 'Bearer ' + user['token']}
                    if iteration % 5 == 4:
                        request = client.post(f"/api/v1/habits/{user['habit_id']}/log",
                            headers=headers, allow_redirects=False,
                            json={'date': datetime.now(UTC).date().isoformat(), 'completed': True})
                    else:
                        request = client.get(paths[iteration % 5], headers=headers, allow_redirects=False)
                    async with request as response:
                        status = str(response.status)
                        body = await response.json()
                        if response.status == 200 and iteration % 5 == 0 and body.get('id') != user['id']:
                            status = 'wrong_identity'
                except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
                    status = type(exc).__name__
                elapsed = time.monotonic() - began
                statuses[status] += 1
                latencies.append(elapsed)
                completed[index] += 1
                if began >= start + args.ramp:
                    plateau.append(elapsed)
                iteration += 1
                await asyncio.sleep(max(0, args.pace - elapsed))
        await asyncio.gather(*(person(index, user) for index, user in enumerate(users)))
    ordered = sorted(plateau or latencies)
    total = sum(statuses.values())
    error_rate = (total - statuses['200']) / max(total, 1)
    p95 = ordered[max(0, math.ceil(len(ordered) * .95) - 1)] if ordered else None
    passed = bool(p95 is not None and p95 < 2 and error_rate < .01 and len(completed) == args.users)
    result = {'profile': 'local synthetic authenticated clients: 80% reads, 20% habit writes',
              'target_users': args.users, 'users_observed': len(completed), 'ramp_seconds': args.ramp,
              'hold_seconds': args.hold, 'seconds_between_actions_per_user': args.pace,
              'requests': total, 'statuses': dict(statuses), 'error_rate': error_rate,
              'plateau_p95_seconds': p95, 'plateau_requests': len(plateau), 'passed': passed,
              'limitations': ['Local hardware, not Azure capacity certification',
                              'Pre-authenticated clients; excludes password login, video and payments',
                              'Synthetic sparse data; repeat with representative data and production-sized staging']}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', type=local_origin, default='http://127.0.0.1:18091')
    parser.add_argument('--clients', type=Path, required=True)
    parser.add_argument('--users', type=int, default=1000)
    parser.add_argument('--ramp', type=int, default=30)
    parser.add_argument('--hold', type=int, default=120)
    parser.add_argument('--pace', type=float, default=5)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not (1 <= args.users <= 10000 and 1 <= args.ramp <= 600 and 10 <= args.hold <= 1800 and args.pace >= 1):
        parser.error('Use bounded users, ramp, hold and at least one second between user actions')
    return asyncio.run(run(args))


if __name__ == '__main__':
    raise SystemExit(main())
