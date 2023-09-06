# This is a python proxy server written with sockets and requests library
# This is some kind of implementation of SOCKS5
# before running this programm enable ip_forwarding on linux machines

import socket
import os
import sys
from threading import Thread
from select import select
import struct

class Proxy():
    def __init__(self) -> None:
        self.socks_version = 5
        # TODO: Implement authentication method
        self.authentication_method = 0
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.proxy_host = "0.0.0.0"
        self.proxy_port = 9999
        self.server_sock.bind((self.proxy_host, self.proxy_port))
        self.server_sock.listen()
    
    def print_server_data(self) -> None:
        print(f"[+] Running proxy server at: {self.proxy_host}:{self.proxy_port}")

    def prepare_addr(self, addr_type : bytes, sock : socket.socket) -> str:
        # address is an ipv4 address followed with 4 bytes address itself
        if addr_type == 1:
            address = sock.recv(4)
            address = socket.inet_ntop(socket.AF_INET, address)
            return address
        # this is a hostname, 1 byte length, then hostname itself
        elif addr_type == 3:
            hostname_length = int(sock.recv(1))
            hostname = sock.recv(hostname_length)
            address = socket.gethostbyname(hostname)
            return address
        # this is an ipv6, but we wont use that
        elif addr_type == 4:
            address = sock.recv(16)
            address = socket.inet_ntop(socket.AF_INET6, address)
            return address
        
    def handle_client(self, sock : socket.socket, addr : tuple) -> None:
        # parsing the initiation packet
        # packet definitions can be found: https://medium.com/@nimit95/socks-5-a-proxy-protocol-b741d3bec66c
        socks_version, authentication_method = sock.recv(2)

        # recieving all available authentication methods
        auth_methods = []
        for _ in range(authentication_method):
            auth_methods.append(ord(sock.recv(1)))
        
        # check if authentication method is supported
        # in this case 0 is authentication without login:password
        if self.authentication_method not in auth_methods:
            print("[!] Authentication method is not allowed!")
            sock.close()
            sys.exit(-1)
        # if everything is ok, send second part of the handshake back to user
        sock.sendall(b"".join(
            [
                self.socks_version.to_bytes(1, 'big'),
                self.authentication_method.to_bytes(1, 'big')
            ]
        ))

        # recieving remote "B" connection data from client "A"
        socks_version, command, reserved, addr_type = sock.recv(4)
        address = self.prepare_addr(addr_type, sock)
        # port number is two bytes long, so reading separately
        port = sock.recv(2)
        port = int.from_bytes(port, 'big')
        
        # command to connect to remote server
        is_ok = False
        try:
            sender_sock = None
            if command == 1:
                # establish a tcp connection to the remote server
                # creating the socket that will send data to the remote server
                socket_type = socket.AF_INET
                if addr_type == 4:
                    socket_type = socket.AF_INET6
                sender_sock = socket.socket(socket_type, socket.SOCK_STREAM)
                sender_sock.connect((address, port))
            else:
                sock.close()
                return
            
            print(f"[+] Connecting to: {address}:{port}")
            remote_addr, remote_port = sender_sock.getsockname()
            # sending packet to client that connection has been established
            packet = b"".join(
                [
                    self.socks_version.to_bytes(1, 'big'), 
                    int(0).to_bytes(1, 'big'),
                    int(0).to_bytes(1, 'big'),
                    int(1).to_bytes(1, 'big'),
                    socket.inet_pton(socket.AF_INET, remote_addr),
                    int(remote_port).to_bytes(2, 'big')
                ]
            )
            sock.sendall(packet)    
            is_ok = True            
        except Exception as e:
            print(f"[!] Error: {e}")
            # if error has occured while connecting to remote server send error packet back to user
            packet = b"".join(
                [
                    self.socks_version.to_bytes(1, 'big'),
                    int(5).to_bytes(1, 'big'),
                    int(0).to_bytes(1, 'big'),
                    int(addr_type).to_bytes(1, 'big'),
                    int(0).to_bytes(4, 'big'),
                    int(0).to_bytes(4, 'big')
                ]
            )
            sock.sendall(packet)

        # check if conection established successfully
        if is_ok and command == 1:
            # run the transaction between client and remote server
            self.run_transaction(sock, sender_sock)
        # at the end close the client connection
        sock.close()

    def run_transaction(self, c_sock : socket.socket, r_sock : socket.socket) -> None:
        while True:
            # switching between client and remote server is they available for reading
            read, _, _ = select([c_sock, r_sock], [], [])
            # check if any of the sockets is available to read
            if not read:
                continue

            for sock in read:
                # recieving data from read available socket
                data = sock.recv(4096)
                if not data:
                    break
                # sending data respectively
                if sock is c_sock:
                    r_sock.send(data)
                else:
                    c_sock.send(data)

    def listen(self) -> None:
        self.print_server_data()
        while True:
            connection = self.server_sock.accept()
            # spawning a new thread with client handler
            sock, addr = connection
            print(f"[+] Connection from: {addr[0]}:{addr[1]}")
            daemon = Thread(target=self.handle_client, args=(sock, addr))
            daemon.daemon = True
            daemon.run()

def main():
    """
    This is a main function to run the proxy server
    """
    try:
        server = Proxy()
        server.listen()
    except KeyboardInterrupt:
        print("[!] Exiting...")
        server.server_sock.close()
        sys.exit(0)

if __name__ == "__main__":
    main()