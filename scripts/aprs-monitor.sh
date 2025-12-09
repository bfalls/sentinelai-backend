#!/usr/bin/env bash
set -euo pipefail

# aprs-monitor.sh
# Simple APRS-IS monitor for macOS using the APRS_* env vars from the backend.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

APRS_HOST="${APRS_HOST:-rotate.aprs.net}"
APRS_PORT="${APRS_PORT:-14580}"
APRS_CALLSIGN="${APRS_CALLSIGN:-N0CALL}"
APRS_PASSCODE="${APRS_PASSCODE:-0}"
APRS_FILTER="${APRS_FILTER:-r/43.615/-116.202/300}"

LOG_DIR="${APRS_LOG_DIR:-logs}"
mkdir -p "$LOG_DIR"
APRS_LOG_FILE="${APRS_LOG_FILE:-$LOG_DIR/aprs-monitor.log}"
export APRS_HOST APRS_PORT APRS_CALLSIGN APRS_PASSCODE APRS_FILTER APRS_LOG_FILE

echo "APRS monitor connecting to ${APRS_HOST}:${APRS_PORT} as ${APRS_CALLSIGN}"
echo "Filter: ${APRS_FILTER}"
echo "Logging to: ${APRS_LOG_FILE}"
echo

python << 'PYCODE'
import datetime
import os
import socket
import time
import traceback

host = os.environ.get("APRS_HOST", "rotate.aprs.net")
port = int(os.environ.get("APRS_PORT", "14580"))
callsign = os.environ.get("APRS_CALLSIGN", "N0CALL")
passcode = os.environ.get("APRS_PASSCODE", "0")
afilter = os.environ.get("APRS_FILTER", "r/43.615/-116.202/100")
log_file = os.environ.get("APRS_LOG_FILE", os.path.join("logs", "aprs-monitor.log"))

login = f"user {callsign} pass {passcode} vers aprs-monitor 0.1"
if afilter.strip():
    login += f" filter {afilter}"
login += "\r\n"
print(login)

def pretty(line: str) -> str:
    line = line.rstrip("\r\n")
    # Server comments start with '#'
    if line.startswith("#"):
        return line
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")
    if ":" in line:
        header, body = line.split(":", 1)
        return f"[{ts}] {header} | {body}"
    return f"[{ts}] {line}"

def run_once():
    # Block indefinitely; let the server push when it has data
    with socket.create_connection((host, port)) as s, \
         open(log_file, "a", encoding="utf-8") as f:
        # Optional: clear any previous timeout, just in case
        s.settimeout(None)

        s.sendall(login.encode("ascii", "ignore"))
        f.write(f"--- Connected to {host}:{port} as {callsign} ---\n")
        f.flush()

        file_obj = s.makefile("r", encoding="utf-8", errors="ignore")

        while True:
            raw = file_obj.readline()
            if not raw:
                # EOF / server closed connection
                break
            out = pretty(raw)
            print(out, flush=True)
            f.write(out + "\n")
            f.flush()

backoff = 5
while True:
    try:
        run_once()
    except KeyboardInterrupt:
        print("Exiting APRS monitor.")
        break
    except Exception:
        ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")
        err = traceback.format_exc().strip()
        msg = f"[{ts}] ERROR: {err}"
        print(msg, flush=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
        time.sleep(backoff)
PYCODE
