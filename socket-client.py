#!/usr/bin/env python3

import socket
import time

HOST = 'monachat.dyndns.org'
PORT = 9095

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

client.connect((HOST, PORT))

client.send(b'MojaChat\0')

time.sleep(1)

client.send(
    '<ENTER room="/MONA8091/.." umax="0" type="tibisii" name="名無しさん" trip="" x="0" y="0" r="100" g="100" b="40" scl="100" stat="通常" attrib="no"/>\0'.encode('utf-8'))

time.sleep(1)

response = client.recv(1024).decode()

for line in response.split('\0'):
    print(line)

client.close()
