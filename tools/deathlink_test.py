"""Death Link test helper.

Joins an Archipelago room as a text-only client on an existing slot, prints every
Death Link it sees, and sends one each time you press Enter, from a made-up source
so the launcher treats it as another player's. Needs the `websockets` package
(Archipelago's requirements include it).

    python tools/deathlink_test.py [ws://localhost:38281] [slot]
"""
import asyncio
import json
import sys
import time

import websockets

SOURCE = "DeathLinkTester"


async def main(uri: str, slot: str) -> None:
    async with websockets.connect(uri, max_size=None) as ws:
        await ws.send(json.dumps([{
            "cmd": "Connect", "game": "", "name": slot, "password": "", "uuid": "deathlink-test",
            "version": {"major": 0, "minor": 6, "build": 8, "class": "Version"},
            "items_handling": 0, "tags": ["TextOnly", "DeathLink"], "slot_data": False,
        }]))

        async def receive() -> None:
            async for raw in ws:
                for packet in json.loads(raw):
                    cmd = packet.get("cmd")
                    if cmd == "Connected":
                        print(f"connected to slot {slot!r}; press Enter to send a Death Link")
                    elif cmd == "ConnectionRefused":
                        print("refused:", packet.get("errors"))
                    elif cmd == "Bounced" and "DeathLink" in packet.get("tags", []):
                        data = packet.get("data", {})
                        mine = " (ours, echoed back)" if data.get("source") == SOURCE else ""
                        print(f"[{time.strftime('%H:%M:%S')}] DEATH LINK from "
                              f"{data.get('source')}: {data.get('cause')}{mine}")

        async def send() -> None:
            loop = asyncio.get_running_loop()
            while True:
                if not await loop.run_in_executor(None, sys.stdin.readline):
                    return  # stdin closed
                await ws.send(json.dumps([{
                    "cmd": "Bounce", "tags": ["DeathLink"],
                    "data": {"time": time.time(), "source": SOURCE,
                             "cause": f"{SOURCE} pressed Enter."},
                }]))
                print(f"[{time.strftime('%H:%M:%S')}] sent a Death Link")

        await asyncio.gather(receive(), send())


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:38281",
                     sys.argv[2] if len(sys.argv) > 2 else "Tester"))
