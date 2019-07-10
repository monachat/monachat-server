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

child_room_user_counts = {}
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

    client_id = None
    client_ip_address = writer.get_extra_info('peername')[0]

    room_path = None
    parent_room_path = None
    room_name = None

    comment_counter = 0

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
                parent_room_path = os.path.dirname(room_path)
                room_name = os.path.basename(room_path)

                if room_path not in room_user_writers:
                    room_user_writers[room_path] = []

                room_user_writers[room_path].append(writer)

                if parent_room_path not in child_room_user_counts:
                    child_room_user_counts[parent_room_path] = {}

                if room_name not in child_room_user_counts[parent_room_path]:
                    child_room_user_counts[parent_room_path][room_name] = 0

                child_room_user_counts[parent_room_path][room_name] += 1
                room_user_count = child_room_user_counts[parent_room_path][room_name]

                if room_path not in room_user_attributes:
                    room_user_attributes[room_path] = {}

                if room_user_attributes[room_path]:
                    writer.write(
                        ('<ROOM>' +
                         ''.join([
                             ('<USER' +
                              ''.join([
                                  f' {key}="{user_attrib[key]}"'
                                  if key in user_attrib else ''
                                  for key in [
                                      'r', 'name', 'id', 'trip', 'ihash', 'stat', 'g', 'type', 'b', 'y', 'x', 'scl']
                              ]) +
                              ' />')
                             for user_id, user_attrib in room_user_attributes[room_path].items()
                         ]) +
                         '</ROOM>\0').encode())
                else:
                    writer.write(b'<ROOM />\0')

                if 'trip' in attrib:
                    attrib['trip'] = tripcode(attrib['trip'])

                room_user_attributes[room_path][client_id] = attrib
                room_user_attributes[room_path][client_id]['id'] = client_id

                if 'attrib' in attrib and attrib['attrib'] == 'no':
                    writer.write(
                        (f'<UINFO name="{attrib["name"]}"' +
                         (f' trip="{attrib["trip"]}"'
                          if 'trip' in attrib else '') +
                         f' id="{client_id}" />\0').encode())

                    if room_path in child_room_user_counts:
                        writer.write(
                            (f'<COUNT c="{room_user_count}" n="{room_name}">' +
                             ''.join([
                                 f'<ROOM c="{child_room_user_count}" n="{child_room_name}" />'
                                 for child_room_name, child_room_user_count in child_room_user_counts[room_path].items()
                             ]) +
                             '</COUNT>\0').encode())

                    write_to_all(
                        room_user_writers[room_path],
                        f'<ENTER id="{client_id}" />',
                    )
                else:
                    room_user_attributes[room_path][client_id]['ihash'] = tripcode(
                        client_ip_address)

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
                    f'<COUNT c="{room_user_count}" n="{room_name}" />',
                )

                if parent_room_path in room_user_writers:
                    write_to_all(
                        room_user_writers[parent_room_path],
                        f'<COUNT><ROOM c="{room_user_count}" n="{room_name}" /></COUNT>',
                    )
            elif root.tag == 'EXIT':
                if room_name is None:
                    writer.write(f'<EXIT id="{client_id}" />\0'.encode())
                else:
                    child_room_user_counts[parent_room_path][room_name] -= 1
                    room_user_count = child_room_user_counts[parent_room_path][room_name]

                    del room_user_attributes[room_path][client_id]

                    write_to_all(
                        room_user_writers[room_path],
                        f'<EXIT id="{client_id}" />',
                    )

                    write_to_all(
                        room_user_writers[room_path],
                        f'<COUNT c="{room_user_count}" n="{room_name}" />',
                    )

                    room_user_writers[room_path].remove(writer)

                    if parent_room_path in room_user_writers:
                        write_to_all(
                            room_user_writers[parent_room_path],
                            f'<COUNT><ROOM c="{room_user_count}" n="{room_name}" /></COUNT>',
                        )

                    comment_counter = 0

                    room_path = None
                    parent_room_path = None
                    room_name = None
            elif root.tag == 'SET':
                if 'x' in attrib and 'y' in attrib and 'scl' in attrib:
                    write_to_all(
                        room_user_writers[room_path],
                        f'<SET x="{attrib["x"]}" scl="{attrib["scl"]}" id="{client_id}" y="{attrib["y"]}" />',
                    )
                elif 'stat' in attrib:
                    write_to_all(
                        room_user_writers[room_path],
                        f'<SET stat="{attrib["stat"]}" id="{client_id}" />',
                    )
                elif 'cmd' in attrib:
                    if 'pre' in attrib and 'param' in attrib:
                        write_to_all(
                            room_user_writers[room_path],
                            f'<SET cmd="{attrib["cmd"]}" pre="{attrib["pre"]}" param="{attrib["param"]}" id="{client_id}" />',
                        )
                    else:
                        write_to_all(
                            room_user_writers[room_path],
                            f'<SET cmd="{attrib["cmd"]}" id="{client_id}" />',
                        )
            elif root.tag == 'RSET':
                write_to_all(
                    room_user_writers[room_path],
                    f'<RSET cmd="{attrib["cmd"]}" param="{attrib["param"]}" id="{client_id}" />',
                )
            elif root.tag == 'COM':
                write_to_all(
                    room_user_writers[room_path],
                    f'<COM cmt="{attrib["cmt"]}" cnt="{comment_counter}" id="{client_id}" />',
                )

                comment_counter += 1
            elif root.tag == 'IG':
                write_to_all(
                    room_user_writers[room_path],
                    f'<IG ihash="{attrib["ihash"]}" stat="{attrib["stat"]}" id="{client_id}" />',
                )
            elif root.tag == 'NOP':
                pass

        await writer.drain()

    if client_id:
        free_ids.insert(0, client_id)
        del logged_ids[client_id]

        if room_name is not None:
            room_user_writers[room_path].remove(writer)

            child_room_user_counts[parent_room_path][room_name] -= 1
            room_user_count = child_room_user_counts[parent_room_path][room_name]

            del room_user_attributes[room_path][client_id]

            write_to_all(
                room_user_writers[room_path],
                f'<EXIT id="{client_id}" />',
            )

            write_to_all(
                room_user_writers[room_path],
                f'<COUNT c="{room_user_count}" n="{room_name}" />',
            )

            if parent_room_path in room_user_writers:
                write_to_all(
                    room_user_writers[parent_room_path],
                    f'<COUNT><ROOM c="{room_user_count}" n="{room_name}" /></COUNT>',
                )

            await writer.drain()

            room_path = None
            parent_room_path = None
            room_name = None

    writer.close()


async def main():
    server = await asyncio.start_server(
        on_connect, HOST, PORT)

    async with server:
        await server.serve_forever()

asyncio.run(main())
