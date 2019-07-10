#!/usr/bin/env python3

import asyncio
import xml.etree.ElementTree as ET

HOST = 'localhost'
PORT = 9095

NUMBER_OF_ROOMS = 100

logged_ids = {}
free_ids = []
max_id = 0

room_user_counts = [0] * NUMBER_OF_ROOMS

room_user_attributes = [{} for i in range(NUMBER_OF_ROOMS)]

room_user_writers = [[] for i in range(NUMBER_OF_ROOMS)]


def write_to_all(writers, message):
    for writer in writers:
        writer.write(f'{message}\0'.encode())


async def on_connect(reader, writer):
    global max_id
    client_id = None
    comment_counter = 0
    current_room_index = None

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

            writer.write(f'+connect id={client_id}\0'.encode())
            writer.write(f'<CONNECT id="{client_id}" />\0'.encode())
        else:
            root = ET.fromstring(decoded_line)
            attrib = root.attrib

            if root.tag == 'policy-file-request':
                pass
            elif root.tag == 'ENTER':
                room_parts = attrib.get('room').split('/')
                room_directory = room_parts[1]

                if len(room_parts) <= 2:
                    writer.write(b'<ROOM />\0')

                    writer.write(
                        f'<UINFO name="{attrib.get("name")}" id="{client_id}" />\0'.encode())

                    writer.write(
                        (f'<COUNT c="1" n="{room_directory}">' +
                         ''.join([
                             f'<ROOM c="{room_user_count}" n="{room_index + 1}" />'
                             for room_index, room_user_count in enumerate(room_user_counts)
                         ]) +
                         '</COUNT>\0').encode())

                    writer.write(f'<ENTER id="{client_id}" />\0'.encode())

                    writer.write(
                        f'<COUNT c="1" n="{room_directory}" />\0'.encode())
                else:
                    room_number = room_parts[2]
                    room_index = int(room_number) - 1
                    current_room_index = room_index

                    room_user_writers[room_index].append(writer)

                    room_user_counts[room_index] += 1

                    if room_user_attributes[room_index]:
                        writer.write(
                            ('<ROOM>' +
                             ''.join([
                                 f'<USER r="{user_attrib.get("r")}" name="{user_attrib.get("name")}" id="{user_id}" ihash="{user_id}" stat="{user_attrib.get("stat")}" g="{user_attrib.get("g")}" type="{user_attrib.get("type")}" b="{user_attrib.get("b")}" y="{user_attrib.get("y")}" x="{user_attrib.get("x")}" scl="{user_attrib.get("scl")}" />'
                                 for user_id, user_attrib in room_user_attributes[room_index].items()
                             ]) +
                             '</ROOM>\0').encode())
                    else:
                        writer.write(b'<ROOM />\0')

                    room_user_attributes[room_index][client_id] = attrib

                    write_to_all(
                        room_user_writers[room_index],
                        f'<ENTER r="{attrib.get("r")}" name="{attrib.get("name")}" id="{client_id}" ihash="{client_id}" stat="{attrib.get("stat")}" g="{attrib.get("g")}" type="{attrib.get("type")}" b="{attrib.get("b")}" y="{attrib.get("y")}" x="{attrib.get("x")}" scl="{attrib.get("scl")}" />',
                    )

                    write_to_all(
                        room_user_writers[room_index],
                        f'<COUNT c="{room_user_counts[room_index]}" n="{room_number}" />',
                    )
            elif root.tag == 'EXIT':
                if current_room_index is None:
                    writer.write(f'<EXIT id="{client_id}" />\0'.encode())
                else:
                    room_user_counts[current_room_index] -= 1
                    del room_user_attributes[current_room_index][client_id]

                    write_to_all(
                        room_user_writers[current_room_index],
                        f'<EXIT id="{client_id}" />',
                    )

                    write_to_all(
                        room_user_writers[room_index],
                        f'<COUNT c="{room_user_counts[room_index]}" n="{current_room_index + 1}" />',
                    )

                    room_user_writers[current_room_index].remove(writer)

                    comment_counter = 0

                    current_room_index = None
            elif root.tag == 'SET':
                if 'x' in attrib and 'y' in attrib and 'scl' in attrib:
                    write_to_all(
                        room_user_writers[current_room_index],
                        f'<SET x="{attrib.get("x")}" scl="{attrib.get("scl")}" id="{client_id}" y="{attrib.get("y")}" />',
                    )
                elif 'stat' in attrib:
                    write_to_all(
                        room_user_writers[current_room_index],
                        f'<SET stat="{attrib.get("stat")}" id="{client_id}" />',
                    )
                elif 'cmd' in attrib:
                    if 'pre' in attrib and 'param' in attrib:
                        write_to_all(
                            room_user_writers[current_room_index],
                            f'<SET cmd="{attrib.get("cmd")}" pre="{attrib.get("pre")}" param="{attrib.get("param")}" id="{client_id}" />',
                        )
                    else:
                        write_to_all(
                            room_user_writers[current_room_index],
                            f'<SET cmd="{attrib.get("cmd")}" id="{client_id}" />',
                        )
            elif root.tag == 'RSET':
                write_to_all(
                    room_user_writers[current_room_index],
                    f'<RSET cmd="{attrib.get("cmd")}" param="{attrib.get("param")}" id="{client_id}" />',
                )
            elif root.tag == 'COM':
                write_to_all(
                    room_user_writers[current_room_index],
                    f'<COM cmt="{attrib.get("cmt")}" cnt="{comment_counter}" id="{client_id}" />',
                )

                comment_counter += 1
            elif root.tag == 'IG':
                write_to_all(
                    room_user_writers[current_room_index],
                    f'<IG ihash="{attrib.get("ihash")}" stat="{attrib.get("stat")}" id="{client_id}" />',
                )
            elif root.tag == 'NOP':
                pass

        await writer.drain()

    if client_id:
        free_ids.insert(0, client_id)
        del logged_ids[client_id]

        if current_room_index is not None:
            room_user_writers[current_room_index].remove(writer)
            room_user_counts[current_room_index] -= 1
            del room_user_attributes[current_room_index][client_id]

            write_to_all(
                room_user_writers[current_room_index],
                f'<EXIT id="{client_id}" />',
            )

            write_to_all(
                room_user_writers[current_room_index],
                f'<COUNT c="{room_user_counts[room_index]}" n="{current_room_index + 1}" />',
            )

            await writer.drain()

            current_room_index = None

    writer.close()


async def main():
    server = await asyncio.start_server(
        on_connect, HOST, PORT)

    async with server:
        await server.serve_forever()

asyncio.run(main())
