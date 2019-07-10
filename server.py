#!/usr/bin/env python3

import asyncio
import crypt
import os
import xml.etree.ElementTree

HOST = 'localhost'
PORT = 9095

NUMBER_OF_ROOMS = 100

RECOGNIZED_ATTRIBUTES = {
    'ENTER': ['r', 'name', 'trip', 'id', 'cmd', 'param', 'ihash', 'pre', 'stat', 'g', 'type', 'b', 'y', 'x', 'scl'],
    'SET': ['x', 'scl', 'stat', 'cmd', 'pre', 'param', 'id', 'y'],
    'RSET': ['cmd', 'param', 'id'],
    'COM': ['cmt', 'cnt', 'style', 'id'],
    'IG': ['ihash', 'stat', 'id'],
}

logged_ids = {}
free_ids = []
max_id = 0

room_user_counts = {}

room_user_attributes = {}
room_user_writers = {}


def tripcode(password):
    salt = (password + 'H.')[1:3]
    return crypt.crypt(password, salt)[-10:]


def write_to_all(writers, message):
    for writer in writers:
        writer.write(f'{message}\0'.encode())


async def on_connect(reader, writer):
    global max_id

    client_ip_address = writer.get_extra_info('peername')[0]
    client_id = None

    room_path = None
    room_directory = None
    room_name = None

    while True:
        try:
            line = await reader.readuntil(b'\0')
        except (asyncio.IncompleteReadError, ConnectionResetError):
            break

        line = line.decode().rstrip('\0')
        print(line)

        if line == 'MojaChat':
            if free_ids:
                client_id = free_ids.pop()
            else:
                max_id += 1
                client_id = max_id

            logged_ids[client_id] = 1

            writer.write(f'+connect id={client_id}\0'.encode())
            writer.write(f'<CONNECT id="{client_id}" />\0'.encode())
        else:
            root = xml.etree.ElementTree.fromstring(line)
            attrib = root.attrib

            attrib['id'] = client_id

            if root.tag == 'policy-file-request':
                pass
            elif root.tag == 'NOP':
                pass
            elif root.tag == 'ENTER':
                room_path = os.path.abspath(attrib['room'])
                room_directory = os.path.dirname(room_path)
                room_name = os.path.basename(room_path)

                if room_path not in room_user_counts:
                    room_user_counts[room_path] = 0

                if 'umax' in attrib:
                    umax = int(attrib['umax'])

                    if umax and room_user_counts[room_path] >= umax:
                        writer.write(b'<FULL />\0')

                        room_path = None
                        room_directory = None
                        room_name = None

                        await writer.drain()

                        continue

                room_user_counts[room_path] += 1

                if room_path not in room_user_writers:
                    room_user_writers[room_path] = []

                room_user_writers[room_path].append(writer)

                if room_path not in room_user_attributes:
                    room_user_attributes[room_path] = {}

                if room_user_attributes[room_path]:
                    writer.write(
                        ('<ROOM>' +
                         ''.join([
                             ('<USER' +
                              ''.join([
                                  f' {key}="{room_user_attribute[key]}"'
                                  if key in room_user_attribute else ''
                                  for key in [
                                      'r', 'name', 'id', 'trip', 'ihash', 'stat', 'g', 'type', 'b', 'y', 'x', 'scl']
                              ]) +
                              ' />')
                             for room_user_attribute in room_user_attributes[room_path].values()
                         ]) +
                         '</ROOM>\0').encode())
                else:
                    writer.write(b'<ROOM />\0')

                if 'trip' in attrib:
                    attrib['trip'] = tripcode(attrib['trip'])

                attrib['ihash'] = tripcode(client_ip_address)

                room_user_attributes[room_path][client_id] = attrib

                if 'attrib' in attrib and attrib['attrib'] == 'no':
                    writer.write(
                        ('<UINFO' +
                         ''.join([
                             f' {key}="{attrib[key]}"'
                             if key in attrib else ''
                             for key in ['name', 'trip', 'id']
                         ]) +
                         ' />\0').encode())

                    child_room_user_counts = {}

                    for child_room_number in range(1, NUMBER_OF_ROOMS + 1):
                        child_room_path = room_path + \
                            '/' + str(child_room_number)

                        if child_room_path in room_user_counts:
                            child_room_user_counts[child_room_number] = room_user_counts[child_room_path]

                    if child_room_user_counts:
                        writer.write(
                            (f'<COUNT c="{room_user_counts[room_path]}" n="{room_name}">' +
                             ''.join([
                                 f'<ROOM c="{child_room_user_count}" n="{child_room_number}" />'
                                 for child_room_number, child_room_user_count in child_room_user_counts.items()
                             ]) +
                             '</COUNT>\0').encode())

                    write_to_all(
                        room_user_writers[room_path],
                        f'<ENTER id="{client_id}" />',
                    )
                else:
                    write_to_all(
                        room_user_writers[room_path],
                        '<ENTER' +
                        ''.join([
                            f' {key}="{attrib[key]}"'
                            if key in attrib else ''
                            for key in RECOGNIZED_ATTRIBUTES['ENTER']
                        ]) +
                        ' />',
                    )

                write_to_all(
                    room_user_writers[room_path],
                    f'<COUNT c="{room_user_counts[room_path]}" n="{room_name}" />',
                )

                if room_directory in room_user_writers:
                    write_to_all(
                        room_user_writers[room_directory],
                        f'<COUNT><ROOM c="{room_user_counts[room_path]}" n="{room_name}" /></COUNT>',
                    )
            elif root.tag == 'EXIT':
                if room_path is None:
                    writer.write(f'<EXIT id="{client_id}" />\0'.encode())
                else:
                    room_user_counts[room_path] -= 1
                    del room_user_attributes[room_path][client_id]

                    write_to_all(
                        room_user_writers[room_path],
                        f'<EXIT id="{client_id}" />',
                    )

                    write_to_all(
                        room_user_writers[room_path],
                        f'<COUNT c="{room_user_counts[room_path]}" n="{room_name}" />',
                    )

                    room_user_writers[room_path].remove(writer)

                    if room_directory in room_user_writers:
                        write_to_all(
                            room_user_writers[room_directory],
                            f'<COUNT><ROOM c="{room_user_counts[room_path]}" n="{room_name}" /></COUNT>',
                        )

                    room_path = None
                    room_directory = None
                    room_name = None
            elif root.tag in RECOGNIZED_ATTRIBUTES:
                write_to_all(
                    room_user_writers[room_path],
                    f'<{root.tag}' +
                    ''.join([
                        f' {key}="{attrib[key]}"'
                        if key in attrib else ''
                        for key in RECOGNIZED_ATTRIBUTES[root.tag]
                    ]) +
                    ' />',
                )

        await writer.drain()

    if client_id:
        free_ids.insert(0, client_id)
        del logged_ids[client_id]

        if room_path is not None:
            room_user_counts[room_path] -= 1
            room_user_writers[room_path].remove(writer)
            del room_user_attributes[room_path][client_id]

            write_to_all(
                room_user_writers[room_path],
                f'<EXIT id="{client_id}" />',
            )

            write_to_all(
                room_user_writers[room_path],
                f'<COUNT c="{room_user_counts[room_path]}" n="{room_name}" />',
            )

            if room_directory in room_user_writers:
                write_to_all(
                    room_user_writers[room_directory],
                    f'<COUNT><ROOM c="{room_user_counts[room_path]}" n="{room_name}" /></COUNT>',
                )

            await writer.drain()

            room_path = None
            room_directory = None
            room_name = None

    writer.close()


async def main():
    server = await asyncio.start_server(
        on_connect, HOST, PORT)

    async with server:
        await server.serve_forever()

asyncio.run(main())
