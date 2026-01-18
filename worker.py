import os
from redis import Redis
from rq import Worker, Queue, Connection

listen = ["default"]

redis_url = os.environ.get("REDIS_URL")
if not redis_url:
    raise RuntimeError("REDIS_URL is not set")

conn = Redis.from_url(redis_url)

if __name__ == "__main__":
    with Connection(conn):
        worker = Worker([Queue(name) for name in listen])
        worker.work()
