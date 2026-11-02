"""Bounded process-group execution; raw output stays in private durable files."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time


def alive(pid, group=False):
    try:
        (os.killpg if group else os.kill)(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def terminate(proc, grace=5):
    # Also check descendants after the group leader exits; never signal other groups.
    if alive(proc.pid, True):
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        proc.poll()  # reap the leader before checking group existence
        if not alive(proc.pid, True):
            return True
        time.sleep(.05)
    if alive(proc.pid, True):
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        proc.wait(timeout=1)
    except subprocess.TimeoutExpired:
        return False
    return not alive(proc.pid, True)


def execute(args, cwd, env, timeout, directory, on_start=None, control=None,
            heartbeat=None, interval=15):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    paths = [directory / name for name in ('stdout.jsonl', 'stderr.txt')]
    start = time.monotonic()
    timed_out = False
    proc = None
    with paths[0].open('xb', buffering=0) as stdout, paths[1].open('xb', buffering=0) as stderr:
        os.chmod(paths[0], 0o600)
        os.chmod(paths[1], 0o600)
        try:
            proc = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                    stdout=stdout, stderr=stderr, start_new_session=True)
            if on_start:
                on_start(proc.pid)
            next_beat = start
            while proc.poll() is None:
                now = time.monotonic()
                if control and control():
                    raise InterruptedError('operator pause/stop requested')
                if now >= next_beat:
                    if heartbeat:
                        heartbeat(dict(pid=proc.pid, elapsed=now-start,
                                       stdout_bytes=paths[0].stat().st_size,
                                       stderr_bytes=paths[1].stat().st_size))
                    next_beat = now + interval
                if now-start >= timeout:
                    timed_out = True
                    break
                time.sleep(min(.1, max(.001, timeout-(now-start))))
        finally:
            terminated = terminate(proc) if proc else False
            for stream in (stdout, stderr):
                os.fsync(stream.fileno())
            (directory / 'process.json').write_text(json.dumps(dict(
                pid=proc.pid if proc else None, timed_out=timed_out,
                terminated=terminated, duration=time.monotonic()-start)))
    return dict(stdout=paths[0].read_text(errors='replace'),
                stderr=paths[1].read_text(errors='replace'),
                timed_out=timed_out, terminated=terminated,
                exit_code=proc.returncode, duration=time.monotonic()-start,
                artifacts=str(directory))
