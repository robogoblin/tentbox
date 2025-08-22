from __future__ import annotations

import asyncio
import aiorwlock
import logging
import os
from typing import Dict, Optional, Union
import RPi.GPIO as GPIO


class Relay:
    """Represents a single relay controlled by one GPIO pin.

    Attributes:
        pin: integer GPIO pin (BCM numbering assumed)
        name: optional friendly name
        active_high: whether setting GPIO True energizes the relay
        state: boolean cached state (True == ON)
    """

    def __init__(
        self, pin: int, name: str = "", active_high: bool = True, initial: bool = False
    ):
        self.pin = pin
        self.name = name or f"relay_{pin}"
        self.active_high = active_high
        self.state = bool(initial)
        self.lock = aiorwlock.RWLock()

        GPIO.setup(self.pin, GPIO.OUT, initial=self._to_hardware_state(self.state))
        self.set(self.state)

        # Hardware setup
        # Ensure GPIO is configured by caller/manager; setup call here is idempotent

    def _to_hardware_state(self, logical_state: bool) -> bool:
        """Convert logical ON/OFF to hardware level considering active_high."""
        return bool(logical_state) if self.active_high else (not bool(logical_state))

    def set(self, on: bool) -> None:
        """Set relay synchronously and update cached state."""
        state = self._to_hardware_state(on)
        GPIO.output(self.pin, state)
        self.state = bool(on)
        logging.debug(
            "Set relay %s(pin=%s) -> %s (state=%s)",
            self.name,
            self.pin,
            self.state,
            state,
        )

    async def async_set(self, on: bool) -> None:
        """Async wrapper that runs the blocking GPIO call in the default executor."""
        loop = asyncio.get_running_loop()
        async with self.lock.writer_lock:
            await loop.run_in_executor(None, self.set, on)

    async def get(self) -> dict[str, any]:
        """Return cached state. Note: does not query hardware."""
        async with self.lock.reader_lock:
            return {
                "pin": self.pin,
                "name": self.name,
                "active_high": self.active_high,
                "state": self.state,
            }


class RelayManager:
    """Manage multiple relays and GPIO lifecycle."""

    def __init__(self, cache: dict, cache_lock: aiorwlock.RWLock):
        """Create manager. gpio_mode: ignored for dummy GPIO; for RPi use 'BCM' or 'BOARD'."""
        self.cache = cache
        self.cache_lock = cache_lock

        # To make things easier we only support BCM mode
        # This means we use the pin GPIO id, not the number of the pin on the boards.
        GPIO.setmode(GPIO.BCM)
        self.relays: Dict[str, Relay] = {}

    def add_relay(
        self,
        id: str,
        pin: int,
        name: Optional[str] = None,
        active_high: bool = True,
        initial: bool = False,
    ):
        self.relays[id] = Relay(
            pin=pin, name=name, active_high=active_high, initial=initial
        )
        logging.info(
            "Added relay %s on pin %s (active_high=%s)", name, pin, active_high
        )

    def set(self, id: str, on: bool) -> None:
        self.relays[id].set(on)
        self.update_cache()

    async def async_set(self, id: str, on: bool) -> None:
        await self.relays[id].async_set(on)
        await self.update_cache()

    async def valid_relay_id(self, id: str) -> bool:
        return True if id in self.relays.keys() else False

    def list_relays(self) -> Dict[str, Dict]:
        return {
            k: {"pin": v.pin, "state": v.state, "name": v.name}
            for k, v in self.relays.items()
        }

    async def update_cache(self):
        async with self.cache_lock.writer_lock:
            self.cache.clear()
            for rid, relay in self.relays.items():
                self.cache[rid] = await relay.get()

    async def update_cache_worker(self):
        """Update cache worker is used to make it feel like one of the mangers.
        I'm not yet convinced that I need it, although I will leave it here for now.
        We already update the cache on every state change, so we don't need this really.
        """
        while True:
            await self.update_cache()
            await asyncio.sleep(5)

    def cleanup(self):
        try:
            GPIO.cleanup()
            logging.info("GPIO cleaned up")
        except Exception:
            logging.exception("GPIO cleanup failed")


# Demo and quick manual test
if __name__ == "__main__":

    async def main():
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        logging.basicConfig(level=getattr(logging, log_level))
        cache = {}
        cache_lock = aiorwlock.RWLock()

        mgr = RelayManager(cache, cache_lock)
        # Example pins; change to your wiring
        mgr.add_relay("plug1", 18, "r1_1", active_high=False, initial=False)
        mgr.add_relay("plug2", 23, "r1_2", active_high=False, initial=False)
        mgr.add_relay("plug3", 24, "r1_3", active_high=False, initial=False)
        mgr.add_relay("plug4", 25, "r1_4", active_high=False, initial=False)
        mgr.add_relay("plug5", 12, "r2_1", active_high=False, initial=False)
        mgr.add_relay("plug6", 16, "r2_2", active_high=False, initial=False)
        mgr.add_relay("plug7", 20, "r2_3", active_high=False, initial=False)
        mgr.add_relay("plug8", 21, "r2_4", active_high=False, initial=False)

        # Turn pump on for 2s, then off
        await mgr.async_set("plug1", True)
        await asyncio.sleep(1)
        await mgr.async_set("plug2", True)
        await asyncio.sleep(1)
        await mgr.async_set("plug3", True)
        await asyncio.sleep(1)
        await mgr.async_set("plug4", True)
        await asyncio.sleep(1)
        await mgr.async_set("plug5", True)
        await asyncio.sleep(1)
        await mgr.async_set("plug6", True)
        await asyncio.sleep(1)
        await mgr.async_set("plug7", True)
        await asyncio.sleep(1)
        await mgr.async_set("plug8", True)

        await asyncio.sleep(2)

        await mgr.async_set("plug1", False)
        await asyncio.sleep(1)
        await mgr.async_set("plug2", False)
        await asyncio.sleep(1)
        await mgr.async_set("plug3", False)
        await asyncio.sleep(1)
        await mgr.async_set("plug4", False)
        await asyncio.sleep(1)
        await mgr.async_set("plug5", False)
        await asyncio.sleep(1)
        await mgr.async_set("plug6", False)
        await asyncio.sleep(1)
        await mgr.async_set("plug7", False)
        await asyncio.sleep(1)
        await mgr.async_set("plug8", False)

        logging.info("States: %s", mgr.list_relays())
        mgr.cleanup()

    asyncio.run(main())
