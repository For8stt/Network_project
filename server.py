import socket
import threading
import struct

from tkinter import Tk
from tkinter import filedialog

import os

MAX_UDP_SIZE = 65507
HEADER_LENGTH=12

CLIENT_MY_IP = "127.0.0.1"
CLIENT_MY_PORT = 50601

CLIENT_SENT_IP = "127.0.0.1"
CLIENT_SENT_PORT = 50602

class Server:
    def __init__(self, ip, port, receiver_ip, receiver_port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP socket creation
        self.receiver_ip = receiver_ip
        self.receiver_port = receiver_port
        self.sock.bind((ip, port))  # Bind to IP and port
        self.running = True
        self.connected = False

    def receive(self):
        while self.running:
            received_fragments = {}
            while True:
                data, addr = self.sock.recvfrom(65535)  # Розмір пакета
                header = struct.unpack('!III', data[:HEADER_LENGTH])  # Розпакування заголовка
                fragment_number, total_fragments, message_type = header
                fragment_data = data[HEADER_LENGTH:]  # Відокремлюємо дані фрагмента

                if message_type == 2:
                    break

                received_fragments[fragment_number] = fragment_data
                print(f"Received fragment {fragment_number + 1}/{total_fragments}: {fragment_data.decode('utf-8')}")

                # Якщо всі фрагменти отримані
                if len(received_fragments) == total_fragments:
                    break

            if not message_type == 2:
                complete_message = b''.join(received_fragments[i] for i in range(total_fragments))

            if message_type == 0:
                print(f"Received message: {complete_message.decode('utf-8', errors='ignore')}")
                if complete_message.decode('utf-8')=='quit':
                    print("Received quit signal, closing connection.")
                    self.running = False
                    self.connected = False
                    self.close()
                    break
            elif message_type == 1:
                self.save_file(complete_message)
                print(f"Received file of size: {len(complete_message)} bytes")
            elif message_type == 2 and not self.connected:
                self.connected = True
                self.send_handshake()

    def save_file(self, file_data):
        save_directory = '/Users/ulian/PycharmProjects/pksPraktika/receive'

        if not os.path.exists(save_directory):
            os.makedirs(save_directory)

        file_name = 'received_file.txt'
        file_path = os.path.join(save_directory, file_name)

        with open(file_path, 'wb') as f:
            f.write(file_data)
        print(f"File saved as: {file_path}")

    def send(self):
        if not self.connected:
            self.send_handshake()

        while self.running:
            message = input("Input message to server (or '1' to send a file):  ")
            if not self.running and not self.connected:
                break
            if not self.connected:
                self.send_handshake()
                print("Waiting for handshake acknowledgment...")
                continue

            if message == '1':
                self.choose_file_and_send()
                continue
            if message=='quit':
                self.connected=False

            message_bytes = message.encode('utf-8')
            total_length = len(message_bytes)

            num_fragments = (total_length // (MAX_UDP_SIZE - HEADER_LENGTH)) + 1

            for i in range(num_fragments):
                start = i * (MAX_UDP_SIZE - HEADER_LENGTH)
                end = min(start + (MAX_UDP_SIZE - HEADER_LENGTH), total_length)
                fragment = message_bytes[start:end]

                header = self.make_header(i, num_fragments, 0)
                packet = header + fragment
                self.sock.sendto(packet, (CLIENT_SENT_IP, CLIENT_SENT_PORT))
                print(f"Sent fragment {i + 1}/{num_fragments}: {fragment.decode('utf-8')}")


    def choose_file_and_send(self):
        root = Tk()
        root.withdraw()

        filw_path = filedialog.askopenfilename()
        if filw_path:
            print(f"Selected file: {filw_path}")
            self.send_file(filw_path)

    def send_file(self, file_path):
        with open(file_path, 'rb') as f:
            file_data = f.read()
            total_length = len(file_data)

            num_fragments = (total_length // (MAX_UDP_SIZE - HEADER_LENGTH)) + 1

            for i in range(num_fragments):
                start = i * (MAX_UDP_SIZE - HEADER_LENGTH)
                end = min(start + (MAX_UDP_SIZE - HEADER_LENGTH), total_length)
                fragment = file_data[start:end]

                header = self.make_header(i, num_fragments, 1)
                packet = header + fragment
                self.sock.sendto(packet, (CLIENT_SENT_IP, CLIENT_SENT_PORT))
                print(f"Sent fragment {i + 1}/{num_fragments}: {fragment}")

    def send_handshake(self):
        packet = self.make_header(0, 1, 2)
        self.sock.sendto(packet, (CLIENT_SENT_IP, CLIENT_SENT_PORT))

    def make_header(self, fragment_number, num_fragments, MESSAGE_TYPE_TEXT):  # MESSAGE_TYPE_TEXT=0 text,  1 is file
        return struct.pack('!III', fragment_number, num_fragments, MESSAGE_TYPE_TEXT)

    def close(self):
        self.sock.close()
        print("Server closed..")



if __name__ == "__main__":
    client = Server(CLIENT_MY_IP, CLIENT_MY_PORT, CLIENT_SENT_IP, CLIENT_SENT_PORT)

    # Start threads for receiving
    receive_thread = threading.Thread(target=client.receive)
    receive_thread.daemon = True  # робимо потік демонічним
    receive_thread.start()

    # Main thread handles sending
    client.send()

    receive_thread.join()
    client.close()
