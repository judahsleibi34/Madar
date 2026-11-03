"""Real Docker concurrency/loopback/cleanup acceptance on a disposable CI runner."""
import json
import os
from pathlib import Path
import selectors
import signal
import socket
import subprocess
import time

from synthetic_postgres import docker, observe, port

SCRIPTS = Path(__file__).resolve().parent
IMAGE = 'postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73'


def main():
    children, scopes = [], []
    occupied = socket.socket()
    try:
        # Reproduce the old failure without killing or adopting any existing user.
        try:
            occupied.bind(('127.0.0.1', 55446))
            occupied.listen(1)
        except OSError as error:
            import errno
            if error.errno != errno.EADDRINUSE:
                raise
        body = '''set -euo pipefail
SCRIPT_DIR="$1"
POSTGRES_IMAGE="$2"
source "$SCRIPT_DIR/synthetic_postgres.sh"
synthetic_postgres_start native-port-regression
printf '%s %s %s\\n' "$CONTAINER_NAME" "$SYNTHETIC_POSTGRES_OWNER" "$SYNTHETIC_POSTGRES_PORT"
read -r done
'''
        for _ in range(2):
            children.append(subprocess.Popen(['bash', '-c', body, 'native', str(SCRIPTS), IMAGE],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True))
        # Bounded startup; retain exact independently generated ownership for
        # supervisor cleanup even when the child is killed after allocation.
        ports = []
        for child in children:
            with selectors.DefaultSelector() as selector:
                selector.register(child.stdout, selectors.EVENT_READ)
                if not selector.select(60):
                    raise RuntimeError('synthetic_postgres_native_start_timeout')
            line = child.stdout.readline().strip().split()
            if len(line) != 3:
                raise RuntimeError('synthetic_postgres_native_start_failed')
            name, owner, observed_port = line
            scope = (name, owner, 'native-port-regression', IMAGE)
            scopes.append(scope)
            record = observe(*scope)
            assert port(record) == observed_port and observed_port != '55446'
            ports.append(observed_port)
            deadline = time.monotonic() + 60
            while True:
                try:
                    docker('exec', record['Id'], 'pg_isready', '-U', 'postgres')
                    break
                except subprocess.CalledProcessError:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(0.25)
            with socket.create_connection(('127.0.0.1', int(observed_port)), timeout=5):
                pass
            assert docker('exec', record['Id'], 'psql', '-X', '-U', 'postgres', '-Atc', 'select 1').strip() == '1'
        assert len(set(ports)) == 2
        # Normal trap cleanup and hard interruption with exact supervisor cleanup.
        children[0].communicate('done\n', timeout=20)
        assert children[0].returncode == 0 and observe(*scopes[0]) is None
        children[1].send_signal(signal.SIGKILL)
        children[1].wait(timeout=10)
        assert children[1].returncode == -signal.SIGKILL
    finally:
        occupied.close()
        for child in children:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=10)
        for scope in scopes:
            record = observe(*scope)
            if record:
                docker('container', 'rm', '-f', record['Id'])
            assert observe(*scope) is None
    print(json.dumps({'native_parallel_postgres': 'PASS', 'occupied_legacy_port': 55446,
        'distinct_loopback_ports': ports, 'normal_and_sigkill_cleanup': 'PASS',
        'removed_owned_containers': len(scopes)}))


if __name__ == '__main__':
    main()
