#!/usr/bin/env python3

import asyncio
import crypt
import os
import xml.etree.ElementTree as ET

HOST = 'localhost'
PORT = 9095

NUMBER_OF_ROOMS = 100

logged_ids = {}
free_ids = []
max_id = 0

room_user_counts = {}

room_user_attribs = {}
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

                if room_path not in room_user_attribs:
                    room_user_attribs[room_path] = {}

                if room_user_attribs[room_path]:
                    writer.write(
                        ('<ROOM>' +
                         ''.join([
                             ('<USER' +
                              ''.join([
                                  f' {key}="{room_user_attrib[key]}"'
                                  if key in room_user_attrib else ''
                                  for key in [
                                      'r', 'name', 'id', 'trip', 'ihash', 'stat', 'g', 'type', 'b', 'y', 'x', 'scl']
                              ]) +
                              ' />')
                             for room_user_attrib in room_user_attribs[room_path].values()
                         ]) +
                         '</ROOM>\0').encode())
                else:
                    writer.write(b'<ROOM />\0')

                attrib['id'] = client_id

                if 'trip' in attrib:
                    attrib['trip'] = tripcode(attrib['trip'])

                attrib['ihash'] = tripcode(client_ip_address)

                room_user_attribs[room_path][client_id] = attrib

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
                            for key in [
                                'r', 'name', 'trip', 'id', 'cmd', 'param', 'ihash', 'pre', 'stat', 'g', 'type', 'b', 'y', 'x', 'scl']
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
                if room_name is None:
                    writer.write(f'<EXIT id="{client_id}" />\0'.encode())
                else:
                    room_user_counts[room_path] -= 1
                    del room_user_attribs[room_path][client_id]

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
            elif root.tag == 'SET':
                write_to_all(
                    room_user_writers[room_path],
                    '<SET' +
                    ''.join([
                        f' {key}="{attrib[key]}"'
                        if key in attrib else ''
                        for key in ['x', 'scl', 'stat', 'cmd', 'pre', 'param']
                    ]) +
                    f' id="{client_id}"' +
                    (f' y="{attrib["y"]}"' if 'y' in attrib else '') +
                    ' />',
                )
            elif root.tag == 'RSET':
                write_to_all(
                    room_user_writers[room_path],
                    '<RSET' +
                    ''.join([
                        f' {key}="{attrib[key]}"'
                        if key in attrib else ''
                        for key in ['cmd', 'param']
                    ]) +
                    f' id="{client_id}" />',
                )
            elif root.tag == 'COM':
                write_to_all(
                    room_user_writers[room_path],
                    '<COM' +
                    ''.join([
                        f' {key}="{attrib[key]}"'
                        if key in attrib else ''
                        for key in ['cmt', 'cnt', 'style']
                    ]) +
                    f' id="{client_id}" />',
                )
            elif root.tag == 'IG':
                write_to_all(
                    room_user_writers[room_path],
                    '<IG' +
                    ''.join([
                        f' {key}="{attrib[key]}"'
                        if key in attrib else ''
                        for key in ['ihash', 'stat']
                    ]) +
                    f' id="{client_id}" />',
                )
            elif root.tag == 'NOP':
                pass

        await writer.drain()

    if client_id:
        free_ids.insert(0, client_id)
        del logged_ids[client_id]

        if room_name is not None:
            room_user_counts[room_path] -= 1
            room_user_writers[room_path].remove(writer)
            del room_user_attribs[room_path][client_id]

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
