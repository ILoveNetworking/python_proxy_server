"""
This is a Proxy server's module
Python implementation os SOCKS5 proxy
"""

import socket
from select import select
import sys
from threading import Thread

class SOCKS5Proxy():
    def __init__(self, bind_host : str = "0.0.0.0", bind_port : int = 9999) -> None:
        self.bind_host = bind_host
        self.bind_port = bind_port
        # proxy without authorization
        self.auth_method = 0
        self.socks_version = 5
        print(f"[+] SOCKS5 Proxy running at: {bind_host}:{bind_port}")

    def __create_socket(self) -> socket.socket:
        """
        This function creates a listener socket, main TCP socket of proxy server
        and binds it to the address and port passed to the init function
        """
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.bind((self.bind_host, self.bind_port))
        return server_sock

    def __listen_connections(self, server_sock : socket.socket) -> None:
        """
        This function listen for incoming connection and spawn a client handling worker thread
        """
        server_sock.listen()
        while True:
            # accept connections from clients
            client_sock, client_addr = server_sock.accept()
            # spawning a worker thread that will handle client activity
            client_thread = Thread(target = self.__handle_client, args = (client_sock, client_addr))
            client_thread.daemon = True
            client_thread.run()

    def __check_auth_method(self, client_sock : socket.socket) -> bool:
        """
        This function recieve "client greeting" packet from client and check if auth type is supported
        """
        # recieve 2 bytes and check all supported auth methods
        socks_version, authentication_method_num = client_sock.recv(2)
        # recieve all available to user auth types
        auth_methods = []
        for _ in range(authentication_method_num):
            auth_methods.append(ord(client_sock.recv(1)))
        # check if noauth is supported
        if self.auth_method not in auth_methods:
            print("[!] Authentication method is not allowed!")
            client_sock.close()
            return False
        # if method is allowed, send "server choice" packet to the client
        client_sock.sendall(b"".join(
            [
                self.socks_version.to_bytes(1, 'big'),
                self.auth_method.to_bytes(1, 'big')
            ]
        ))
        return True

    def __prepare_address(self, client_sock : socket.socket) -> tuple:
        """
        This function recieve "SOCKS5 address" packet with address type: 1 IPv4, 3 Domain name, 4 IPv6 from client
        and then recieves another packet with address itself based on address type. Also recieves port from client
        Function returns a connection data and command to the SOCKS server, addres type: ("ip", port, command, addr_type)
        """
        try:
            # recieving a "client connection request" packet and parsing it
            _, command, _, addr_type = client_sock.recv(4)

            # address is an ipv4 address followed with 4 bytes address itself
            if addr_type == 1:
                address = client_sock.recv(4)
                address = socket.inet_ntop(socket.AF_INET, address)
            # this is a hostname, 1 byte is hostname length, then hostname itself
            elif addr_type == 3:
                hostname_length = int(client_sock.recv(1))
                hostname = client_sock.recv(hostname_length)
                address = socket.gethostbyname(hostname)
            # this is an ipv6, but we wont use that
            elif addr_type == 4:
                address = client_sock.recv(16)
                address = socket.inet_ntop(socket.AF_INET6, address)
            
            # recieving port from the client
            # port number is two bytes long, so reading separately
            port = client_sock.recv(2)
            port = int.from_bytes(port, 'big')

            return (address, port, command, addr_type)
        except ValueError:
            return None

    def __success_packet(self, dst_sock : socket.socket, client_sock : socket.socket, addr_type : int) -> bool:
        """
        This function forms and sends packet if connection to remote server was established successfully
        """
        dst_addr, dst_port = dst_sock.getsockname()
        sock_type = socket.AF_INET
        if addr_type == 4:
            sock_type = socket.AF_INET6

        packet = b"".join([
            self.socks_version.to_bytes(1, 'big'), # socks version (5)
            b'\x00', # request granted code (0)
            b'\x00', # reserved byte (0)
            addr_type.to_bytes(1, 'big'), # address type from dst server (1)
            socket.inet_pton(sock_type, dst_addr), # address in network byte order format
            int(dst_port).to_bytes(2, 'big') # dst port number 2 bytes long
        ])
        # send the packet to the client
        try:
            client_sock.send(packet)
        except Exception as e:
            print(f"Error: {e}")
            return False
        return True

    def __error_packet(self, client_sock : socket.socket, addr_type : int) -> bool:
        """
        This function forms and sends packet if connection to remote server was not established
        """
        packet = b"".join([
            self.socks_version.to_bytes(1, 'big'), # socks version (5)
            b'\x05', # connection refused by remote host (1)
            b'\x00', # reserved byte (0)
            addr_type.to_bytes(1, 'big'), # address type from dst server (1)
            b'\x00\x00\x00\x00', # zeroes as an address
            b'\x00\x00\x00\x00' # zeroes as port number
        ])
        # send the packet to the client
        try:
            client_sock.send(packet)
        except Exception as e:
            print(f"Error: {e}")
            return False
        return True

    def __transact(self, client_sock : socket.socket, dest_sock : socket.socket) -> None:
        """
        This function runs a transaction loop in which client and destination server exchanges their data
        """
        while True:
            read, _, _ = select([client_sock, dest_sock], [], [], 1)
        
            if not read:
                break

            # if client ready to send data
            if client_sock in read:
                data = client_sock.recv(4096)
                if dest_sock.send(data) <= 0:
                    break
            # if destination server ready to send data
            if dest_sock in read:
                data = dest_sock.recv(4096)
                if client_sock.send(data) <= 0:
                    break

    def __handle_client(self, client_sock : socket.socket, client_addr : tuple) -> None:
        """
        This function handles the client connection and provide SOCKS5 protocol
        """
        if not self.__check_auth_method(client_sock):
            return
        
        address_data = self.__prepare_address(client_sock)
        if not address_data:
            return
        dst_host, dst_port, cmd, address_type = address_data

        try:
            # check if command is TCP/IP connection establish
            if cmd == 1:
                # establish a tcp connection to the remote server
                # creating the socket that will send data to the remote server
                socket_type = socket.AF_INET
                # if address type is 4 use ipv6
                if address_type == 4:
                    socket_type = socket.AF_INET6
                dst_sock = socket.socket(socket_type, socket.SOCK_STREAM)
                dst_sock.connect((dst_host, dst_port))

                print(f"[+] Connecting to: {dst_host}:{dst_port}")
                # sending a successful packet to the client
                if not self.__success_packet(dst_sock, client_sock, address_type):
                    return
                # if everything successful start exchange data between client and dectination server
                self.__transact(client_sock, dst_sock)

            else:
                client_sock.close()
                return
        except Exception as e:
            print(f"[!] Error: {e}")
            if not self.__error_packet(client_sock, address_type):
                return
            return

    def run(self) -> None:
        """
        This is a main function that accept client connections
        """
        try:
            s_sock = self.__create_socket()
            self.__listen_connections(s_sock)
        except KeyboardInterrupt:
            s_sock.close()
            print("\n[+] Exiting!")
            sys.exit(0)


if __name__ == "__main__":
    p = SOCKS5Proxy()
    p.run()