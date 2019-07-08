#!/usr/bin/env python3

import asyncio
import time

HOST = 'localhost'
PORT = 9095


async def main():
    reader, writer = await asyncio.open_connection(
        HOST, PORT)

    writer.write(b'MojaChat\0')

    writer.write(
        '<ENTER room="/MONA8094" name="名無しさん" attrib="no"/>\0'.encode('utf-8'))

    response = await reader.readuntil(b'\0')
    print(response.decode())

    time.sleep(10)

    writer.close()


asyncio.run(main())
