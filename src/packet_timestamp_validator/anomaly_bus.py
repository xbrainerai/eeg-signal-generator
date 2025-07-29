import asyncio

# Shared global event queue for anomaly events
anomaly_queue = asyncio.Queue()

async def publish_anomaly(event: dict):
    """
    Publishes an anomaly event to the shared queue.
    
    Args:
        event (dict): Anomaly event with keys like:
            - type
            - severity
            - channel_id
            - ts_curr
            - ts_prev
            - delta
    """
    await anomaly_queue.put(event)
