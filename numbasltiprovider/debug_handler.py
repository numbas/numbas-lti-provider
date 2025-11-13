import asyncio
from contextlib import aclosing, closing

from asgiref.sync import sync_to_async

from django.conf import settings
from django.core import signals
from django.core.handlers.asgi import get_script_prefix
from django.core.exceptions import RequestAborted
from django.urls import set_script_prefix
from django.utils.functional import cached_property

from redis import asyncio as aioredis
from datetime import datetime

pool = aioredis.ConnectionPool.from_url(settings.CHANNEL_LAYERS['default']['CONFIG']['hosts'][0])
c = aioredis.Redis.from_pool(pool)

from contextlib import asynccontextmanager

@asynccontextmanager
async def debug_request(scope, body_file):
    s = None

    if scope['type'] == 'http':
        try:
            def format_host(h):
                host, port = h
                return f'{host}:{port}'

            body = body_file.read()
            body_file.seek(0)

            data = {
                'method': scope['method'],
                'path': scope['path'],
                'query_string': scope['query_string'],
                'server': format_host(scope['server']),
                'client': format_host(scope['client']),
                'time': datetime.now().isoformat(),
                'body': body,
            }
            await c.incr('daphne_debug_request_count')
            s = await c.xadd('daphne_debug', data)
        except Exception as e:
            print(e)

    yield

    if s is not None:
        await c.xdel('daphne_debug', s)

from django.core.asgi import ASGIHandler
class DebugASGIHandler(ASGIHandler):

    async def handle(self, scope, receive, send):
        """
        Handles the ASGI request. Called via the __call__ method.
        """
        # Receive the HTTP request body as a stream object.
        try:
            body_file = await self.read_body(receive)
        except RequestAborted:
            return

        async with debug_request(scope, body_file):
            # Request is complete and can be served.
            set_script_prefix(get_script_prefix(scope))
            await signals.request_started.asend(sender=self.__class__, scope=scope)
            # Get the request and check for basic issues.
            request, error_response = self.create_request(scope, body_file)
            if request is None:
                body_file.close()
                await self.send_response(error_response, send)
                await sync_to_async(error_response.close)()
                return

            async def process_request(request, send):
                response = await self.run_get_response(request)
                try:
                    await self.send_response(response, send)
                except asyncio.CancelledError:
                    # Client disconnected during send_response (ignore exception).
                    pass

                return response

            # Try to catch a disconnect while getting response.
            tasks = [
                # Check the status of these tasks and (optionally) terminate them
                # in this order. The listen_for_disconnect() task goes first
                # because it should not raise unexpected errors that would prevent
                # us from cancelling process_request().
                asyncio.create_task(self.listen_for_disconnect(receive)),
                asyncio.create_task(process_request(request, send)),
            ]
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            # Now wait on both tasks (they may have both finished by now).
            for task in tasks:
                if task.done():
                    try:
                        task.result()
                    except RequestAborted:
                        # Ignore client disconnects.
                        pass
                    except AssertionError:
                        body_file.close()
                        raise
                else:
                    # Allow views to handle cancellation.
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        # Task re-raised the CancelledError as expected.
                        pass

            try:
                response = tasks[1].result()
            except asyncio.CancelledError:
                await signals.request_finished.asend(sender=self.__class__)
            else:
                await sync_to_async(response.close)()

            body_file.close()
