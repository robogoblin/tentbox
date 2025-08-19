import asyncio
import logging
import os
import json
from datetime import datetime
from time import time

# Optional hardware library for DS18B20 on Raspberry Pi
try:
    from w1thermsensor import W1ThermSensor, SensorNotReadyError, NoSensorFoundError

    _W1_AVAILABLE = True
except Exception:
    _W1_AVAILABLE = False


class DS18B20Sensor:
    """Represents a single DS18B20 sensor.

    If the w1thermsensor library is available the class will use real
    readings. Otherwise it simulates readings so the code is runnable on
    non-RPi machines.
    """

    def __init__(
        self, sensor_id: str | None = None, name: str = "", interval: int = 15
    ):
        """Create a sensor wrapper.

        sensor_id: optional device id (as returned by W1) or None to auto-discover.
        name: human friendly name
        interval: how often to attempt a read (seconds)
        """
        self.sensor_id = sensor_id
        self.name = name or (f"ds18b20_{sensor_id}" if sensor_id else "ds18b20")
        self.interval = interval
        self.temperature = None
        self.timestamp = 0.0
        self.location = ""
        self.lock = asyncio.Lock()

        if _W1_AVAILABLE:
            try:
                if sensor_id:
                    self._hw = W1ThermSensor(sensor_id=sensor_id)
                else:
                    # will raise NoSensorFoundError if none
                    self._hw = W1ThermSensor()
            except Exception as e:
                logging.warning("Failed to initialize W1 sensor %s: %s", sensor_id, e)
                self._hw = None
        else:
            self._hw = None

    async def output(self) -> dict:
        async with self.lock:
            return {
                "name": self.name,
                "location": self.location,
                "temperature": self.temperature,
                "timestamp": self.timestamp,
                "readable_time": (
                    datetime.fromtimestamp(self.timestamp).strftime("%Y-%m-%d %H:%M:%S")
                    if self.timestamp
                    else None
                ),
            }

    def load_config(self, given_config: dict):
        if "name" in given_config:
            self.name = given_config["name"]
        if "location" in given_config:
            self.location = given_config["location"]

    def set_location(self, location: str):
        self.location = location

    def set_name(self, name: str):
        self.name = name

    async def start_reading(self):
        """Start a perpetual read loop for this sensor. Call with create_task.

        This is an async coroutine that never exits (intended to be scheduled
        as a background task). It writes the latest reading into the object's
        attributes protected by an asyncio.Lock.
        """
        while True:
            logging.debug("DS18B20 %s: attempting read", self.name)
            try:
                if self._hw:
                    # synchronous library call inside async coroutine - acceptable
                    # because the driver is fast; if it blocks too long consider
                    # running it in a thread executor.
                    temp_c = self._hw.get_temperature()
                else:
                    # simulated value
                    temp_c = 20.0 + (os.getpid() % 5) + (time() % 1)

                async with self.lock:
                    self.temperature = temp_c
                    self.timestamp = time()

                logging.debug("DS18B20 %s: read temperature=%.2f", self.name, temp_c)

            except (SensorNotReadyError, NoSensorFoundError) as e:
                logging.debug("DS18B20 %s: sensor busy or not found: %s", self.name, e)
            except Exception as e:
                logging.exception(
                    "DS18B20 %s: unexpected error reading sensor: %s", self.name, e
                )

            await asyncio.sleep(self.interval)


class DS18B20Manager:
    """Manage multiple DS18B20 sensors and update a shared cache.

    The manager expects a mutable mapping (dict-like) and an asyncio.Lock to
    be supplied by the caller. The manager will update that dict in-place so
    other code holding a reference sees updates.
    """

    def __init__(self, cache: dict, lock: asyncio.Lock, read_interval: int = 15):
        self.cache = cache
        self.lock = lock
        self.read_interval = read_interval
        self.sensors: dict[str, DS18B20Sensor] = {}

    async def add_sensor(self, sensor_ids: list[str | None]):
        for sid in sensor_ids:
            sensor = DS18B20Sensor(sensor_id=sid, interval=self.read_interval)
            # start the sensor read loop inside this event loop
            asyncio.create_task(sensor.start_reading())
            key = sid or sensor.name
            self.sensors[key] = sensor

    async def read_sensors(self):
        """Aggregate sensor outputs and write them into the shared cache."""
        while True:
            output = {}
            for key, sensor in self.sensors.items():
                data = await sensor.output()
                output[key] = data
                logging.debug("Sensor %s data: %s", key, data)

            async with self.lock:
                self.cache.clear()
                self.cache.update(output)

            await asyncio.sleep(self.read_interval)


if __name__ == "__main__":

    async def main():
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        logging.basicConfig(level=getattr(logging, log_level))

        logging.info("Starting DS18B20 manager demo")

        # Example sensors - on real Pi you could pass device ids. None will auto-discover.
        sensors = ["28-000000b239d5", "28-000000b23b5a"]
        cache = {}
        lock = asyncio.Lock()
        manager = DS18B20Manager(cache, lock)

        await manager.add_sensor(sensors)
        # run aggregator in background
        asyncio.create_task(manager.read_sensors())

        # Demo loop prints cache every interval
        while True:
            await asyncio.sleep(manager.read_interval)
            logging.info(json.dumps(cache, indent=2))

    asyncio.run(main())
