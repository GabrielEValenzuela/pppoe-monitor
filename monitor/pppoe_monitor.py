#!/usr/bin/env python3
import os
import time
import requests
from datetime import datetime
from librouteros import connect

# === ENVIRONMENT CONFIG ===
ROUTER_IP = os.getenv("ROUTER_IP", "192.168.88.1")
ROUTER_USER = os.getenv("ROUTER_USER", "admin")
ROUTER_PASS = os.getenv("ROUTER_PASS", "yourpassword")
INFLUX_URL = os.getenv(
    "INFLUX_URL", "http://influxdb:8086/api/v2/write?org=netmon&bucket=pppoe"
)
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "your_influx_token")
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", 5))  # seconds


# === CONNECT TO ROUTEROS ===
def get_pppoe_clients():
    """Fetch active PPPoE sessions using MikroTik API."""
    try:
        api = connect(username=ROUTER_USER, password=ROUTER_PASS, host=ROUTER_IP)
        clients = []
        for entry in api.path("ppp", "active"):
            clients.append(
                {
                    "name": entry.get("name"),
                    "address": entry.get("address"),
                    "service": entry.get("service"),
                    "uptime": entry.get("uptime"),
                    "caller_id": entry.get("caller-id"),
                }
            )
        return clients
    except Exception as e:
        print(f"[ERROR] MikroTik API connection failed: {e}")
        return []


def get_interface_traffic():
    """Fetch per-interface RX/TX byte counters."""
    try:
        api = connect(username=ROUTER_USER, password=ROUTER_PASS, host=ROUTER_IP)
        traffic = {}
        for iface in api.path("interface"):
            traffic[iface.get("name")] = {
                "rx": int(iface.get("rx-byte", 0)),
                "tx": int(iface.get("tx-byte", 0)),
            }
        return traffic
    except Exception as e:
        print(f"[WARN] Interface stats failed: {e}")
        return {}


def push_influx(measurement, tags, fields):
    """Send metrics to InfluxDB (line protocol)."""
    line = (
        f"{measurement},{','.join([f'{k}={v}' for k, v in tags.items()])} "
        + ",".join([f"{k}={v}" for k, v in fields.items()])
    )
    try:
        headers = {"Authorization": f"Token {INFLUX_TOKEN}"}
        r = requests.post(INFLUX_URL, data=line, headers=headers, timeout=3)
        if r.status_code >= 300:
            print(f"[WARN] Influx write failed ({r.status_code}): {r.text}")
    except Exception as e:
        print(f"[ERROR] Influx push failed: {e}")


# === MAIN LOOP ===
def main():
    print("[INFO] Starting lightweight PPPoE monitor...")
    last_traffic = {}

    while True:
        clients = get_pppoe_clients()
        iface_traffic = get_interface_traffic()

        # Calculate per-interface bandwidth (bps)
        if last_traffic:
            for iface, stats in iface_traffic.items():
                if iface in last_traffic:
                    rx_bps = (
                        (stats["rx"] - last_traffic[iface]["rx"]) * 8 / POLL_INTERVAL
                    )
                    tx_bps = (
                        (stats["tx"] - last_traffic[iface]["tx"]) * 8 / POLL_INTERVAL
                    )
                    push_influx(
                        "interface_bw",
                        {"router": ROUTER_IP, "interface": iface},
                        {"rx_bps": rx_bps, "tx_bps": tx_bps},
                    )

        # Push PPPoE client count
        push_influx("pppoe_clients", {"router": ROUTER_IP}, {"count": len(clients)})

        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] Clients: {len(clients)} | Interfaces: {len(iface_traffic)}"
        )
        last_traffic = iface_traffic
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
