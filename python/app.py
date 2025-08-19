import asyncio
import logging
import os
from quart import Quart, jsonify, send_from_directory, request
import board

import ds18b20
import dht22
import relays


app = Quart(__name__)

# Shared cache for sensor data (in-process)
sensor_cache: dict = {"dht22": {}, "ds18b20": {}, "relays": {}, "relayNames": []}
sensor_lock = asyncio.Lock()


async def start_managers():
    ### This will be moved out to config ###
    ds18b20_sensors = ["28-000000b239d5", "28-000000b23b5a"]
    dht22_sensors = [
        {"pin": board.D13, "name": "test1"},
        {"pin": board.D19, "name": "test2"},
        {"pin": board.D26, "name": "test3"},
    ]
    relay_config = [
        {"pin": 18, "name": "r1"},
        {"pin": 23, "name": "r2"},
        {"pin": 24, "name": "r3"},
        {"pin": 25, "name": "r4"},
        {"pin": 12, "name": "r5"},
        {"pin": 16, "name": "r6"},
        {"pin": 20, "name": "r7"},
        {"pin": 21, "name": "r8"},
    ]
    ### End Move to config ###

    # Start DHT22 manager
    dht_manager = dht22.DHT22Manager(sensor_cache["dht22"], sensor_lock)
    for dht22_sensor in dht22_sensors:
        await dht_manager.add_sensor(
            pin=dht22_sensor["pin"], name=dht22_sensor.get("name", "")
        )
    app.add_background_task(dht_manager.read_sensors)
    logging.info("DHT22Manager started")

    # Start DS18B20 manager

    ds18b20_manager = ds18b20.DS18B20Manager(sensor_cache["ds18b20"], sensor_lock)
    await ds18b20_manager.add_sensor(ds18b20_sensors)
    # autodiscover a couple sensors where possible
    app.add_background_task(ds18b20_manager.read_sensors)
    logging.info("DS18B20Manager started")
    # Start relays manager and register some example relays
    relay_mgr = relays.RelayManager()
    for relay in relay_config:
        relay_mgr.add_relay(**relay)


@app.before_serving
async def startup():
    await start_managers()


@app.route("/api/sensors")
async def get_sensors():
    async with sensor_lock:
        # return a shallow copy to avoid serialization races
        return jsonify(
            {k: dict(v) if isinstance(v, dict) else v for k, v in sensor_cache.items()}
        )


@app.route("/api/relay", methods=["POST"])
async def post_relay():
    form = await request.form
    idx_raw = form.get("index")
    state_raw = form.get("state")
    if idx_raw is None or state_raw is None:
        return ("bad request", 400)
    try:
        idx = int(idx_raw)
        state = bool(int(state_raw))
    except Exception:
        return ("bad request", 400)

    # normalize index: frontend may send 0-based or 1-based; try both
    keys = getattr(app, "relay_keys", [])
    target_key = None
    if keys:
        if 1 <= idx <= len(keys):
            target_key = keys[idx - 1]
        elif 0 <= idx < len(keys):
            target_key = keys[idx]
    if not target_key:
        return ("relay not found", 404)

    try:
        await app.relay_mgr.async_set(target_key, state)
        return ("ok", 204)
    except Exception:
        logging.exception("Failed to set relay %s", target_key)
        return ("internal error", 500)


@app.route("/api/relay-default", methods=["POST"])
async def post_relay_default():
    # placeholder for setting relay default behaviour (not implemented)
    return ("not implemented", 501)


# Serve static files at root (e.g., /index.html, /styles.css)
@app.route("/<path:filename>")
async def static_files(filename):
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    return await send_from_directory(static_dir, filename)


@app.route("/")
async def root():
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    return await send_from_directory(static_dir, "index.html")


if __name__ == "__main__":
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, log_level))
    app.run(host="0.0.0.0")
