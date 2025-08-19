"""Relay control helpers for optocoupler relays.

Provides:
- Relay: small wrapper for one relay pin (state caching, active_high toggle)
- RelayManager: manage multiple Relay instances, safe GPIO init/cleanup

Usage:
    from relays import RelayManager
    mgr = RelayManager()
    mgr.add_relay(17, "fan", active_high=False)
    mgr.set("fan", True)

Async usage (safe from async code):
    await mgr.async_set("fan", True)

The module uses RPi.GPIO if available; otherwise a dummy implementation
is used so code runs on non-RPi machines for development.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Dict, Optional, Union

# Try to import real RPi.GPIO; provide a dummy if unavailable for dev/testing
try:
    import RPi.GPIO as GPIO  # type: ignore

    _HAS_GPIO = True
except Exception:
    _HAS_GPIO = False


class _DummyGPIO:
    BCM = "BCM"
    OUT = "OUT"

    def __init__(self):
        self._pin_state = {}

    def setmode(self, mode):
        logging.debug("DummyGPIO: setmode(%s)", mode)

    def setup(self, pin, mode, initial=False):
        logging.debug("DummyGPIO: setup pin=%s mode=%s initial=%s", pin, mode, initial)
        self._pin_state[pin] = bool(initial)

    def output(self, pin, value):
        logging.debug("DummyGPIO: output pin=%s value=%s", pin, value)
        self._pin_state[pin] = bool(value)

    def input(self, pin):
        return self._pin_state.get(pin, False)

    def cleanup(self):
        logging.debug("DummyGPIO: cleanup")
        self._pin_state.clear()


GPIO = GPIO if _HAS_GPIO else _DummyGPIO()


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
        self.lock = asyncio.Lock()

        # Hardware setup
        # Ensure GPIO is configured by caller/manager; setup call here is idempotent
        GPIO.setup(self.pin, GPIO.OUT, initial=self._to_hw(self.state))

    def _to_hw(self, logical_state: bool) -> bool:
        """Convert logical ON/OFF to hardware level considering active_high."""
        return bool(logical_state) if self.active_high else (not bool(logical_state))

    def set(self, on: bool) -> None:
        """Set relay synchronously and update cached state."""
        hw = self._to_hw(on)
        GPIO.output(self.pin, hw)
        self.state = bool(on)
        logging.debug(
            "Set relay %s(pin=%s) -> %s (hw=%s)", self.name, self.pin, self.state, hw
        )

    async def async_set(self, on: bool) -> None:
        """Async wrapper that runs the blocking GPIO call in the default executor."""
        loop = asyncio.get_running_loop()
        async with self.lock:
            await loop.run_in_executor(None, self.set, on)

    def toggle(self) -> None:
        self.set(not self.state)

    async def async_toggle(self) -> None:
        await self.async_set(not self.state)

    def get(self) -> bool:
        """Return cached state. Note: does not query hardware."""
        return self.state


class RelayManager:
    """Manage multiple relays and GPIO lifecycle."""

    def __init__(self, gpio_mode: Optional[str] = None):
        """Create manager. gpio_mode: ignored for dummy GPIO; for RPi use 'BCM' or 'BOARD'."""
        self.relays: Dict[str, Relay] = {}
        self._initialized = False
        self._gpio_mode = gpio_mode or os.getenv("GPIO_MODE", "BCM")
        self._init_gpio()

    def _init_gpio(self):
        if not self._initialized:
            # For real RPi.GPIO use constants; for dummy it will accept the value
            try:
                if _HAS_GPIO:
                    if self._gpio_mode == "BCM":
                        GPIO.setmode(GPIO.BCM)
                    else:
                        GPIO.setmode(GPIO.BOARD)
                else:
                    GPIO.setmode(self._gpio_mode)
                self._initialized = True
                logging.debug("GPIO initialized mode=%s", self._gpio_mode)
            except Exception as e:
                logging.exception("Failed to initialize GPIO: %s", e)

    def add_relay(
        self,
        pin: int,
        name: Optional[str] = None,
        active_high: bool = True,
        initial: bool = False,
    ) -> Relay:
        key = name or str(pin)
        if key in self.relays:
            raise KeyError(f"Relay with key '{key}' already exists")
        relay = Relay(pin=pin, name=key, active_high=active_high, initial=initial)
        self.relays[key] = relay
        logging.info("Added relay %s on pin %s (active_high=%s)", key, pin, active_high)
        return relay

    def set(self, key_or_pin: Union[str, int], on: bool) -> None:
        key = str(key_or_pin)
        if key not in self.relays:
            # try pin lookup
            for r in self.relays.values():
                if r.pin == int(key_or_pin):
                    r.set(on)
                    return
            raise KeyError(f"Relay {key_or_pin} not found")
        self.relays[key].set(on)

    async def async_set(self, key_or_pin: Union[str, int], on: bool) -> None:
        key = str(key_or_pin)
        if key in self.relays:
            await self.relays[key].async_set(on)
            return
        for r in self.relays.values():
            if r.pin == int(key_or_pin):
                await r.async_set(on)
                return
        raise KeyError(f"Relay {key_or_pin} not found")

    def get(self, key_or_pin: Union[str, int]) -> bool:
        key = str(key_or_pin)
        if key in self.relays:
            return self.relays[key].get()
        for r in self.relays.values():
            if r.pin == int(key_or_pin):
                return r.get()
        raise KeyError(f"Relay {key_or_pin} not found")

    def toggle(self, key_or_pin: Union[str, int]) -> None:
        key = str(key_or_pin)
        if key in self.relays:
            self.relays[key].toggle()
            return
        for r in self.relays.values():
            if r.pin == int(key_or_pin):
                r.toggle()
                return
        raise KeyError(f"Relay {key_or_pin} not found")

    async def async_toggle(self, key_or_pin: Union[str, int]) -> None:
        await self.async_set(key_or_pin, not self.get(key_or_pin))

    def list_relays(self) -> Dict[str, Dict]:
        return {
            k: {"pin": v.pin, "state": v.state, "active_high": v.active_high}
            for k, v in self.relays.items()
        }

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

        mgr = RelayManager()
        # Example pins; change to your wiring
        mgr.add_relay(18, "r1_1", active_high=False, initial=False)
        mgr.add_relay(23, "r1_2", active_high=False, initial=False)
        mgr.add_relay(24, "r1_3", active_high=False, initial=False)
        mgr.add_relay(25, "r1_4", active_high=False, initial=False)
        mgr.add_relay(12, "r2_1", active_high=False, initial=False)
        mgr.add_relay(16, "r2_2", active_high=False, initial=False)
        mgr.add_relay(20, "r2_3", active_high=False, initial=False)
        mgr.add_relay(21, "r2_4", active_high=False, initial=False)

        # Turn pump on for 2s, then off
        await mgr.async_set("r1_1", True)
        await asyncio.sleep(1)
        await mgr.async_set("r1_2", True)
        await asyncio.sleep(1)
        await mgr.async_set("r1_3", True)
        await asyncio.sleep(1)
        await mgr.async_set("r1_4", True)
        await asyncio.sleep(1)
        await mgr.async_set("r2_1", True)
        await asyncio.sleep(1)
        await mgr.async_set("r2_2", True)
        await asyncio.sleep(1)
        await mgr.async_set("r2_3", True)
        await asyncio.sleep(1)
        await mgr.async_set("r2_4", True)

        await asyncio.sleep(2)

        await mgr.async_set("r1_1", False)
        await asyncio.sleep(1)
        await mgr.async_set("r1_2", False)
        await asyncio.sleep(1)
        await mgr.async_set("r1_3", False)
        await asyncio.sleep(1)
        await mgr.async_set("r1_4", False)
        await asyncio.sleep(1)
        await mgr.async_set("r2_1", False)
        await asyncio.sleep(1)
        await mgr.async_set("r2_2", False)
        await asyncio.sleep(1)
        await mgr.async_set("r2_3", False)
        await asyncio.sleep(1)
        await mgr.async_set("r2_4", False)

        logging.info("States: %s", mgr.list_relays())
        mgr.cleanup()

    asyncio.run(main())
