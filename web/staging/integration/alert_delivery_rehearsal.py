#!/usr/bin/env python3
"""Exercise collection, evaluation, delivery and recovery on loopback fixtures.

No production destination or configuration is accepted. Delivery is at least
once on transport failure; the receiver deduplicates the bounded event identity.
"""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import socket
import threading
from urllib.request import Request, build_opener, ProxyHandler

SPEC = importlib.util.spec_from_file_location('worker_observer', Path(__file__).resolve().parents[2] / 'scripts/inspect_notification_worker.py')
observer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(observer)


class Delivery:
    """Tiny fixture evaluator: acknowledge state only after successful delivery."""
    def __init__(self, sink):
        self.sink = sink
        self.active = set()
        self.pending = None
        self.sequence = 0

    def update(self, report):
        current = set(report['alerts'])
        events = [{'code': code, 'state': state} for state, codes in
                  (('firing', current - self.active), ('resolved', self.active - current)) for code in sorted(codes)]
        if self.pending is None and events:
            self.sequence += 1
            body = {'fixture': 'madar-phase4-alert-delivery', 'sequence': self.sequence, 'events': events}
            body['event_id'] = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
            self.pending = body
        if self.pending is not None:
            # The only receiver is created by this process on a random loopback
            # port. No proxy, redirect, user destination or credentials exist.
            request = Request(self.sink, data=json.dumps(self.pending).encode(), headers={'Content-Type': 'application/json'}, method='POST')
            with build_opener(ProxyHandler({}), observer.NoRedirect()).open(request, timeout=3) as response:
                if response.status != 204:
                    raise RuntimeError('Synthetic alert sink rejected event')
            for event in self.pending['events']:
                (self.active.add if event['state'] == 'firing' else self.active.discard)(event['code'])
            self.pending = None
        return events


def rehearse():
    if socket.gethostname() != 'madar-staging':
        raise RuntimeError('Dedicated staging VM required before opening fixtures')
    metrics = {name: 0 for name in observer.NAMES}
    metrics.update(ownership_lost=1, acknowledgement_failed=1, queue_depth=10, oldest_pending_age_seconds=600)
    received = {}; attempts = []; reject = [True]

    class Worker(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            self.send_response(200); self.end_headers()
            if self.path == '/health': self.wfile.write(b'{"status":"ok","consuming":true}')
            elif self.path == '/metrics':
                self.wfile.write(('\n'.join(observer.PREFIX + key + ' ' + str(value) for key, value in metrics.items())).encode())

    class Sink(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 4096:
                self.send_error(413); return
            packet = json.loads(self.rfile.read(size)); attempts.append(packet['event_id'])
            if reject[0]:
                reject[0] = False; self.send_response(503); self.end_headers(); return
            received[packet['event_id']] = packet
            self.send_response(204); self.end_headers()

    servers = [ThreadingHTTPServer(('127.0.0.1', 0), handler) for handler in (Worker, Sink)]
    threads = [threading.Thread(target=server.serve_forever, daemon=True) for server in servers]
    for thread in threads: thread.start()
    try:
        base = 'http://127.0.0.1:' + str(servers[0].server_port)
        delivery = Delivery('http://127.0.0.1:' + str(servers[1].server_port) + '/synthetic')
        first = observer.inspect(base, 'a' * 64, True)
        try: delivery.update(first)
        except __import__('urllib.error', fromlist=['HTTPError']).HTTPError as error:
            if error.code != 503: raise
        else: raise AssertionError('Injected failed alert delivery was accepted')
        assert not delivery.active and delivery.pending is not None
        delivery.update(first)
        assert attempts[0] == attempts[1] and len(received) == 1
        delivery.update(first)
        assert len(attempts) == 2, 'Repeated firing alerts must be suppressed'
        metrics.update(queue_depth=0, oldest_pending_age_seconds=0)
        clear = observer.inspect(base, 'a' * 64, True, previous=first)
        assert clear['status'] == 'PASS'
        delivery.update(clear); delivery.update(clear)
        assert not delivery.active and len(received) == 2 and len(attempts) == 3
        return {'scope': 'loopback synthetic signal-to-delivery drill', 'status': 'PASS',
                'signals': first['alerts'], 'failed_delivery_retried': True, 'stable_event_id': True,
                'firing_duplicate_suppressed': True, 'recovery_delivered_once': True,
                'accepted_packets': len(received), 'post_attempts': len(attempts),
                'production_destination_configured': False,
                'limitations': ['fixture signals, not a production collector', 'no durable process-restart delivery state',
                                'no production routing or alert integration authorized']}
    finally:
        for server in servers: server.shutdown(); server.server_close()
        for thread in threads: thread.join(timeout=3)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('INSPECT', 'REHEARSE'), default='INSPECT', nargs='?')
    args = parser.parse_args()
    print(json.dumps(rehearse() if args.mode == 'REHEARSE' else {'mode': 'INSPECT', 'mutations': False, 'production_delivery': False}, sort_keys=True))
