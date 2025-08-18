import asyncio
from quart import Quart, jsonify, send_from_directory
from multiprocessing import Manager
import os


mgr = Manager()
dht22_cache = mgr.dict()


app = Quart(__name__)

# Shared cache for sensor data
data_cache = {}
data_lock = asyncio.Lock()


# Example background worker
def create_worker(name, interval):
    async def worker():
        while True:
            # Simulate reading sensor data
            value = f"{name}_value"
            async with data_lock:
                data_cache[name] = value
            await asyncio.sleep(interval)

    return worker


# Register multiple workers
async def start_workers():
    workers = [
        create_worker("sensor1", 2),
        create_worker("sensor2", 3),
    ]
    for w in workers:
        app.add_background_task(w)


@app.before_serving
async def startup():
    await start_workers()


@app.route("/api/data")
async def get_data():
    async with data_lock:
        return jsonify(data_cache)


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
    app.run(host="0.0.0.0")
