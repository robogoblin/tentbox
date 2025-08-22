import adafruit_dht
import asyncio
import aiorwlock
import board
import json
import logging
import os
from datetime import datetime
from time import time

import board_index


# TODO
# Sensors need to be initialized with their pin and name.
# We need functions on the manager to update the sensors it is controlling.


class DHT22Sensor:
    def __init__(self, pin: int, name: str = ""):
        self.pin = pin
        self.sensor = adafruit_dht.DHT22(
            board_index.get_pin(self.pin), use_pulseio=False
        )
        self.name = "name" if name else f"dht22_{pin}"
        self.location = ""
        self.temperature = 0.0
        self.humidity = 0.0
        self.timestamp = 0.0
        self.lock = aiorwlock.RWLock()

    async def output(self) -> dict:
        async with self.lock.reader_lock:
            return {
                "temperature": self.temperature,
                "humidity": self.humidity,
                "timestamp": self.timestamp,
                "readable_time": datetime.fromtimestamp(self.timestamp).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            }

    async def load_config(self, given_config: dict):
        async with self.lock.writer_lock:
            if "name" in given_config:
                self.name = given_config["name"]
            if "location" in given_config:
                self.location = given_config["location"]

    async def set_location(self, location: str):
        async with self.lock.writer_lock:
            self.location = location

    async def set_name(self, name: str):
        async with self.lock.writer_lock:
            self.name = name

    async def start_reading(self):
        while True:
            logging.debug(f"Reading DHT22 sensor on pin {self.pin}")
            try:
                temp_c = self.sensor.temperature
                hum = self.sensor.humidity
                if (temp_c is not None) and (hum is not None):
                    async with self.lock.writer_lock:
                        self.humidity = hum
                        self.temperature = temp_c
                        self.timestamp = time()
                logging.debug(f"Read DHT22 sensor on pin {self.pin}: {temp_c}C, {hum}%")
            except Exception as e:
                # CRC/timeouts are normal sometimes—just retry after a short delay
                logging.debug(f"Error reading DHT22 sensor on pin {self.pin}: {e}")
            await asyncio.sleep(5)


# A manager is responsible for reading the various dht22 sensors that we have available.
# We can have more than one. They are added to the manager once the class is initilized.
# Sensors can have a name on them. We store the names and other details so they persist
# reboots.
# We expect that when we start the caller will give us defaults. If we find a file, we
# use that to override the data found.
# When a sensor config is updated we will write the config to a json file on disk.
# We do readings every 15 seconds and cache the results. We expect that there will
# be many failures when doing readings, we'll just cache the success results.
# The manager is expected to run in a separate process and share a cache with the
# web server. Although not strictly required.
# Because of this we expect the caller to supply a dict that we can use to cache
# data in.
class DHT22Manager:
    def __init__(self, cache: dict, cache_lock: aiorwlock.RWLock):

        self.cache = cache
        self.cache_lock = cache_lock
        self.sensors = {}

    async def add_sensor(self, pin: int, name: str = "", location: str = ""):
        sensor = DHT22Sensor(pin, name)
        await sensor.set_location(location)
        asyncio.create_task(sensor.start_reading())
        self.sensors[f"{pin}"] = sensor

    async def read_sensors(self):
        while True:
            logging.debug(f"Reading DHT22 sensors")
            output = {}

            for key, sensor in self.sensors.items():
                data = await sensor.output()
                output[key] = data
                logging.debug(f"Sensor {key} data: {data}")

            async with self.cache_lock.writer_lock:
                self.cache.update(output)

            await asyncio.sleep(15)


if __name__ == "__main__":

    async def main():
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        logging.basicConfig(level=getattr(logging, log_level))
        logging.info("Starting... It takes a bit of time to get the first reading...")
        sensors = [
            {"pin": 13, "name": "test1"},
            {"pin": 19, "name": "test2"},
            {"pin": 26, "name": "test3"},
        ]
        cache = {}
        cache_lock = aiorwlock.RWLock()
        manager = DHT22Manager(cache, cache_lock)

        for sensor_config in sensors:
            await manager.add_sensor(
                pin=sensor_config["pin"], name=sensor_config.get("name", "")
            )

        asyncio.create_task(manager.read_sensors())

        while True:
            await asyncio.sleep(15)
            logging.info(json.dumps(cache, indent="  "))

    asyncio.run(main())
