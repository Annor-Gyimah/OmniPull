from concurrent.futures import ThreadPoolExecutor


# Central thread pool for all long-running background tasks
executor = ThreadPoolExecutor(max_workers=10)