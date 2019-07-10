#!/usr/bin/env python3

import asyncio
import time

HOST = 'localhost'
PORT = 9095


async def main():
    reader, writer = await asyncio.open_connection(
        HOST, PORT)

    writer.write(b'MojaChat\0')

    writer.write(b'<policy-file-request/>\0')

    writer.write(
        '<ENTER room="/MONA8094" name="名無しさん" attrib="no"/>\0'.encode('utf-8'))

    '''writer.write(b'<EXIT />\0')

    writer.write(
        '<ENTER room="/MONA8094/1" umax="0" type="tibisii" name="名無しさん" x="81" y="325" r="100" g="100" b="100" scl="100" stat="通常" />\0'.encode('utf-8'))'''

    while True:
        response = await reader.readuntil(b'\0')
        print(response.decode())

    writer.close()


asyncio.run(main())
