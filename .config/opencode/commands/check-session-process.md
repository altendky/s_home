---
description: Check an opencode session process tree for activity, hangs, and executable paths
---

# Check Session Process

**Root PID:** $ARGUMENTS

Inspect a running opencode session process and all of its descendants to determine whether the tree appears active, idle, or hung. This command is read-only: do not send signals, kill processes, attach debuggers, or modify files.

## Process

1. Parse the root PID from `$ARGUMENTS`. If no PID is provided, ask the user for the PID and wait.
2. Run the diagnostic script below with the root PID. It recursively discovers descendants through `/proc`, prints executable paths and command lines, then samples CPU, context-switch, I/O, memory, state, and wait-channel counters over five seconds.
3. Summarize the process tree and call out:
   - the root process identity and elapsed runtime
   - all descendants grouped as a tree
   - executable path, cwd, and argv for `agentic-mcp` processes
   - processes in concerning states (`D`, `Z`, stopped/traced states, or unexpectedly missing)
   - which processes showed recent CPU/context-switch/I/O activity
   - whether the tree appears active, normally idle, or plausibly hung
4. Keep the final report concise and include the evidence used for the assessment.

## Diagnostic Script

Run this with the Bash tool, replacing `<pid>` with the parsed root PID:

```bash
python3 - '<pid>' <<'PY'
import os
import shlex
import sys
import time
from collections import defaultdict

if len(sys.argv) != 2 or not sys.argv[1].isdigit():
    raise SystemExit('usage: python3 process_check.py <pid>')

root = int(sys.argv[1])
page_size = os.sysconf('SC_PAGE_SIZE')
clock_ticks = os.sysconf(os.sysconf_names['SC_CLK_TCK'])


def read_text(path):
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except FileNotFoundError:
        return None
    except PermissionError:
        return '<permission denied>'


def read_link(path):
    try:
        return os.readlink(path)
    except FileNotFoundError:
        return '<missing>'
    except PermissionError:
        return '<permission denied>'
    except OSError as error:
        return f'<{error}>'


def cmdline(pid):
    try:
        raw = open(f'/proc/{pid}/cmdline', 'rb').read().rstrip(b'\0')
    except FileNotFoundError:
        return []
    except PermissionError:
        return ['<permission denied>']
    if not raw:
        return []
    return [part.decode('utf-8', 'replace') for part in raw.split(b'\0')]


def quoted_cmdline(pid):
    args = cmdline(pid)
    return ' '.join(shlex.quote(arg) for arg in args) if args else '<empty>'


def stat_fields(pid):
    stat = read_text(f'/proc/{pid}/stat')
    if not stat:
        return None
    after = stat.rsplit(')', 1)[1].strip().split()
    return {
        'state': after[0],
        'ppid': int(after[1]),
        'pgrp': int(after[2]),
        'session': int(after[3]),
        'utime': int(after[11]),
        'stime': int(after[12]),
        'threads': int(after[17]),
        'starttime': int(after[19]),
        'rss_pages': int(after[21]),
    }


def comm(pid):
    value = read_text(f'/proc/{pid}/comm')
    return value.strip() if value else '<missing>'


def children_by_parent():
    children = defaultdict(list)
    for name in os.listdir('/proc'):
        if not name.isdigit():
            continue
        pid = int(name)
        fields = stat_fields(pid)
        if fields:
            children[fields['ppid']].append(pid)
    for values in children.values():
        values.sort()
    return children


def walk_tree(pid, children, depth=0):
    rows = [(pid, depth)]
    for child in children.get(pid, []):
        rows.extend(walk_tree(child, children, depth + 1))
    return rows


def elapsed(pid, fields):
    uptime_text = read_text('/proc/uptime')
    if not uptime_text:
        return '<unknown>'
    uptime = float(uptime_text.split()[0])
    seconds = max(0, int(uptime - fields['starttime'] / clock_ticks))
    hours, rem = divmod(seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours:
        return f'{hours}h{minutes:02d}m{seconds:02d}s'
    return f'{minutes}m{seconds:02d}s'


def io_values(pid):
    values = {'read_bytes': 0, 'write_bytes': 0}
    content = read_text(f'/proc/{pid}/io')
    if not content or content == '<permission denied>':
        return values
    for line in content.splitlines():
        key, _, value = line.partition(':')
        if key in values:
            values[key] = int(value.strip())
    return values


def context_switches(pid):
    values = {'voluntary_ctxt_switches': 0, 'nonvoluntary_ctxt_switches': 0}
    content = read_text(f'/proc/{pid}/status') or ''
    for line in content.splitlines():
        key, _, value = line.partition(':')
        if key in values:
            values[key] = int(value.strip())
    return values


def fd_count(pid):
    try:
        return len(os.listdir(f'/proc/{pid}/fd'))
    except (FileNotFoundError, PermissionError):
        return 0


def snapshot(pid):
    fields = stat_fields(pid)
    if not fields:
        return None
    ctx = context_switches(pid)
    io = io_values(pid)
    return {
        'pid': pid,
        'ppid': fields['ppid'],
        'pgrp': fields['pgrp'],
        'session': fields['session'],
        'state': fields['state'],
        'threads': fields['threads'],
        'cpu_ticks': fields['utime'] + fields['stime'],
        'rss_mb': fields['rss_pages'] * page_size / 1024 / 1024,
        'wchan': (read_text(f'/proc/{pid}/wchan') or '').strip(),
        'comm': comm(pid),
        'exe': read_link(f'/proc/{pid}/exe'),
        'cwd': read_link(f'/proc/{pid}/cwd'),
        'argv': quoted_cmdline(pid),
        'fds': fd_count(pid),
        **ctx,
        **io,
    }


if not os.path.exists(f'/proc/{root}'):
    raise SystemExit(f'PID {root} does not exist')

children = children_by_parent()
tree = walk_tree(root, children)
pids = [pid for pid, _depth in tree]

first = {pid: snapshot(pid) for pid in pids}
time.sleep(5)
second = {pid: snapshot(pid) for pid in pids}

print('PROCESS TREE')
for pid, depth in tree:
    snap = second.get(pid) or first.get(pid)
    prefix = '  ' * depth
    if not snap:
        print(f'{prefix}{pid} <exited>')
        continue
    print(f"{prefix}{pid} {snap['comm']} state={snap['state']} elapsed={elapsed(pid, stat_fields(pid))} argv={snap['argv']}")

print('\nEXECUTABLE PATHS')
for pid in pids:
    snap = second.get(pid) or first.get(pid)
    if not snap:
        continue
    print(f"{pid} {snap['comm']}")
    print(f"  exe: {snap['exe']}")
    print(f"  cwd: {snap['cwd']}")
    print(f"  argv: {snap['argv']}")

print('\nACTIVITY SAMPLE over 5 seconds')
print('PID     PPID   ST THR CPUΔs  CTXΔ  RΔ(MB) WΔ(MB) RSS(MB) FDS WCHAN                 COMM')
for pid in pids:
    before = first.get(pid)
    after = second.get(pid)
    if before and not after:
        print(f'{pid:<7} exited during sample')
        continue
    if not after:
        print(f'{pid:<7} missing')
        continue
    base = before or after
    cpu_delta = (after['cpu_ticks'] - base['cpu_ticks']) / clock_ticks
    ctx_delta = (
        after['voluntary_ctxt_switches'] + after['nonvoluntary_ctxt_switches']
        - base['voluntary_ctxt_switches'] - base['nonvoluntary_ctxt_switches']
    )
    read_delta = (after['read_bytes'] - base['read_bytes']) / 1024 / 1024
    write_delta = (after['write_bytes'] - base['write_bytes']) / 1024 / 1024
    print(
        f"{pid:<7} {after['ppid']:<6} {after['state']:<2} {after['threads']:<3} "
        f"{cpu_delta:>5.2f} {ctx_delta:>6} {read_delta:>7.2f} {write_delta:>7.2f} "
        f"{after['rss_mb']:>7.1f} {after['fds']:>3} {after['wchan'][:20]:<20} {after['comm']}"
    )

print('\nAGENTIC-MCP EXECUTABLES')
found_agentic_mcp = False
for pid in pids:
    snap = second.get(pid) or first.get(pid)
    if not snap:
        continue
    if snap['comm'] == 'agentic-mcp' or 'agentic-mcp' in snap['argv'] or snap['exe'].endswith('/agentic-mcp'):
        found_agentic_mcp = True
        print(f"{pid}: exe={snap['exe']} cwd={snap['cwd']} argv={snap['argv']}")
if not found_agentic_mcp:
    print('<none found>')

print('\nSTATE LEGEND')
print('R=running, S=sleeping/interruptible wait, D=uninterruptible I/O wait, Z=zombie, T/t=stopped or traced')
PY
```

## Assessment Guidance

- `R` or nonzero CPU/context-switch deltas indicate recent activity.
- `S` in `ep_poll`, `futex_do_wait`, or `do_wait` is usually normal idle/waiting behavior for event loops, worker pools, and shells waiting on children.
- `D` is concerning if it persists across samples because the process is stuck in uninterruptible kernel I/O.
- `Z` means a zombie process waiting to be reaped.
- `T` or `t` means stopped/traced and should be explained by a debugger/job-control action.
- A model/provider subprocess can look mostly idle while waiting on network or model output; distinguish that from a hard hang by checking whether the parent or worker still has CPU/context-switch activity and whether there are error logs or stuck states.
