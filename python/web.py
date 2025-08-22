import asyncio
import aiorwlock
import quart
import quart_schema
import logging
import os
import typing
from dataclasses import dataclass

import relays


@dataclass
class SetRelaySchema:
    relay_id: str
    state: str


# @dataclass
# class GetSensorsSchema:


def create_app(
    hw_manager_function: typing.Callable,
    sensor_cache: dict,
    cache_lock: aiorwlock.RWLock,
    relay_mgr: relays.RelayManager,
) -> quart.Quart:
    app = quart.Quart(__name__)
    sensor_cache = sensor_cache
    cache_lock = cache_lock
    hardware_manager = hw_manager_function
    quart_schema.QuartSchema(app)

    @app.before_serving
    async def startup():
        await hardware_manager()

    @app.route("/api/sensors")
    async def get_sensors():
        async with cache_lock.reader_lock:
            # return a shallow copy to avoid serialization races
            return quart.jsonify(
                {
                    k: dict(v) if isinstance(v, dict) else v
                    for k, v in sensor_cache.items()
                }
            )

    @app.route("/api/relay", methods=["POST"])
    # @quart_schema.document_response(None, status_code=201)
    async def post_relay():
        pass

    @app.route("/api/relay/state", methods=["POST"])
    @quart_schema.validate_request(SetRelaySchema)
    async def post_relay_default(data):
        try:
            data = await quart.request.get_json()
            relay_id = data.get("relay_id")
            state = data.get("state")
            if relay_id is None or state is None:
                logging.warning("Missing parameters on relay state set")
                return ("bad request", 400)
            state = state.lower()
            if state == "on":
                usable_state = True
            elif state == "off":
                usable_state = False
            else:
                logging.warning(
                    f"Invalid state value on relay state set: {state}",
                )
                return ("bad request", 400)

            if not await relay_mgr.valid_relay_id(relay_id):
                logging.warning(f"Invalid relay id on relay state set: {relay_id}")
                return ("relay not found", 404)

            await relay_mgr.async_set(relay_id, usable_state)
            return ("ok", 204)
        except Exception:
            logging.exception(f"Failed to set relay {relay_id}")
            return ("internal error", 500)

    # Serve static files at root (e.g., /index.html, /styles.css)
    @app.route("/<path:filename>")
    async def static_files(filename):
        static_dir = os.path.join(os.path.dirname(__file__), "static")
        return await quart.send_from_directory(static_dir, filename)

    @app.route("/")
    async def root():
        static_dir = os.path.join(os.path.dirname(__file__), "static")
        return await quart.send_from_directory(static_dir, "index.html")

    return app
