import asyncio
import json
import sys
import logging

from oriv_mcp.schemas.rpc import JSONRPCRequest
from oriv_mcp.server.rpc_router import handle_rpc

logger = logging.getLogger(__name__)


async def process_stdio_message(line: str):
    try:
        raw = json.loads(line)

        request = JSONRPCRequest(**raw)

        response = await handle_rpc(request)

        encoded = json.dumps(
            response.model_dump(),
            ensure_ascii=False,
        )

        # IMPORTANT:
        # stdout is reserved for JSON-RPC only
        print(encoded, flush=True)

    except Exception as e:
        error_response = {
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,
                "message": str(e),
            },
            "id": None,
        }

        print(
            json.dumps(error_response),
            flush=True,
        )


async def stdio_loop():
    """
    Background STDIO RPC listener.
    """

    logger.info("STDIO listener started")

    loop = asyncio.get_running_loop()

    while True:
        try:
            line = await loop.run_in_executor(
                None,
                sys.stdin.readline,
            )

            if not line:
                await asyncio.sleep(0.1)
                continue

            line = line.strip()

            if not line:
                continue

            await process_stdio_message(line)

        except asyncio.CancelledError:
            logger.info("STDIO listener stopped")
            break

        except Exception:
            logger.exception("STDIO loop failure")
