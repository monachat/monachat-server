#!/usr/bin/env python3

import asyncio
import xml.etree.ElementTree as ET

HOST = 'localhost'
PORT = 9095

logged_ids = {}
free_ids = []
max_id = 0


async def on_connect(reader, writer):
    global max_id
    client_id = None

    while True:
        try:
            line = await reader.readuntil(b'\0')
        except (asyncio.IncompleteReadError, ConnectionResetError):
            break

        decoded_line = line.decode().rstrip('\0')
        print(decoded_line)

        if decoded_line == 'MojaChat':
            if free_ids:
                client_id = free_ids.pop()
            else:
                max_id += 1
                client_id = max_id

            logged_ids[client_id] = 1
            print(list(logged_ids.keys()))

            writer.write(b'+connect id=%d\0' % client_id)
        else:
            root = ET.fromstring(decoded_line)

            if root.tag == 'ENTER':
                print(root.attrib)

        await writer.drain()

    free_ids.insert(0, client_id)
    del logged_ids[client_id]

    writer.close()


async def main():
    server = await asyncio.start_server(
        on_connect, HOST, PORT)

    async with server:
        await server.serve_forever()

asyncio.run(main())
