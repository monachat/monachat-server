#!/usr/bin/env python3

import asyncio
import xml.etree.ElementTree as ET

HOST = 'localhost'
PORT = 843


async def on_connect(reader, writer):
    while True:
        try:
            line = await reader.readuntil(b'\0')
        except (asyncio.IncompleteReadError, ConnectionResetError):
            break

        decoded_line = line.decode().rstrip('\0')
        print(decoded_line)

        root = ET.fromstring(decoded_line)

        if root.tag == 'policy-file-request':
            writer.write(
                b'<cross-domain-policy><allow-access-from domain="monachat.dyndns.org" to-ports="843,9090-9100" /><allow-access-from domain="monachat.net" to-ports="843,9090-9100" /><allow-access-from domain="chat.moja.jp" to-ports="843,9090-9100" /><allow-access-from domain="cool.moja.jp" to-ports="843,9090-9100" /></cross-domain-policy>\0')

            await writer.drain()

    writer.close()


async def main():
    server = await asyncio.start_server(
        on_connect, HOST, PORT)

    async with server:
        await server.serve_forever()

asyncio.run(main())
