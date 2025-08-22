import asyncio
import aiorwlock
import logging
import os

import ds18b20
import dht22
import relays
import web


# Shared cache for sensor data (in-process)
sensor_cache: dict = {"dht22": {}, "ds18b20": {}, "relays": {}}
cache_lock = aiorwlock.RWLock()

dht_manager = dht22.DHT22Manager(sensor_cache["dht22"], cache_lock)
ds18b20_manager = ds18b20.DS18B20Manager(sensor_cache["ds18b20"], cache_lock)
relay_mgr = relays.RelayManager(sensor_cache["relays"], cache_lock)


async def start_managers():
    ### This will be moved out to config ###
    ds18b20_sensors = ["000000b239d5", "000000b23b5a"]
    dht22_sensors = [
        {"pin": 13, "name": "test1"},
        {"pin": 19, "name": "test2"},
        {"pin": 26, "name": "test3"},
    ]
    relay_config = [
        {"id": "plug1", "pin": 18, "name": "r1"},
        {"id": "plug2", "pin": 23, "name": "r2"},
        {"id": "plug3", "pin": 24, "name": "r3"},
        {"id": "plug4", "pin": 25, "name": "r4"},
        {"id": "plug5", "pin": 12, "name": "r5"},
        {"id": "plug6", "pin": 16, "name": "r6"},
        {"id": "plug7", "pin": 20, "name": "r7"},
        {"id": "plug8", "pin": 21, "name": "r8"},
    ]
    ### End Move to config ###

    # Start DHT22 manager

    for dht22_sensor in dht22_sensors:
        await dht_manager.add_sensor(
            pin=dht22_sensor["pin"], name=dht22_sensor.get("name", "")
        )
    app.add_background_task(dht_manager.read_sensors)
    logging.info("DHT22Manager started")

    # Start DS18B20 manager

    await ds18b20_manager.add_sensor(ds18b20_sensors)
    # autodiscover a couple sensors where possible
    app.add_background_task(ds18b20_manager.read_sensors)
    logging.info("DS18B20Manager started")
    # Start relays manager and register some example relays

    for relay in relay_config:
        relay_mgr.add_relay(**relay)
    app.add_background_task(relay_mgr.update_cache_worker)


app = web.create_app(start_managers, sensor_cache, cache_lock, relay_mgr)

if __name__ == "__main__":
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, log_level))
    app.run(host="0.0.0.0")
