import asyncio


class AsyncTaskManager:
    def __init__(self, loop):
        self.loop = loop

    def cancel_all_tasks(self):
        to_cancel = asyncio.all_tasks(self.loop)
        if not to_cancel:
            return

        for task in to_cancel:
            task.cancel()

        self.loop.run_until_complete(asyncio.gather(*to_cancel, return_exceptions=True))

        for task in to_cancel:
            if task.cancelled():
                continue
            if task.exception() is not None:
                self.loop.call_exception_handler(
                    {
                        "message": "unhandled exception during asyncio.run() shutdown",
                        "exception": task.exception(),
                        "task": task,
                    }
                )
