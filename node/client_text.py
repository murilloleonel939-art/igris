import asyncio, json, os, websockets

URL = os.environ["IGRIS_URL"]      # wss://tu-direccion/ws
TOKEN = os.environ["NODE_TOKEN"]


async def main():
    async with websockets.connect(
        URL, additional_headers={"Authorization": f"Bearer {TOKEN}"}
    ) as ws:
        print("Conectado con Igris. Escribe 'salir' para terminar.")
        while True:
            text = await asyncio.to_thread(input, "Tú: ")
            if text.strip().lower() == "salir":
                break
            await ws.send(json.dumps({"text": text}))
            reply = json.loads(await ws.recv())
            print("Igris:", reply["say"])

asyncio.run(main())
