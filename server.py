import socket
import threading
import struct

from tkinter import Tk
from tkinter import filedialog
import time

import os

MAX_UDP_SIZE = 1472
HEADER_LENGTH=12
SAVE_DIRECTORY='/Users/ulian/PycharmProjects/pksPraktika/receive'


CLIENT_MY_IP = "127.0.0.1"
CLIENT_MY_PORT = 50601

CLIENT_SENT_IP = "127.0.0.1"
CLIENT_SENT_PORT = 50602

class Server:
    WINDOW_SIZE = 4

    def __init__(self, ip, port, receiver_ip, receiver_port):
        self.receive_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Socket for receiving
        self.send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Socket for sending
        self.receiver_ip = receiver_ip
        self.receiver_port = receiver_port
        self.receive_sock.bind((ip, port))  # Bind to IP and port
        self.running = True
        self.connected = False

        self.window = {}
        self.base = 0

    def receive(self):
        while self.running:
            received_fragments = {}
            file_name = None

            expected_seq_num = 0
            window = {}

            while True:
                try:
                    data, addr = self.receive_sock.recvfrom(MAX_UDP_SIZE)
                    header = struct.unpack('!III', data[:HEADER_LENGTH])  # Розпакування заголовка

                    fragment_number, total_fragments, message_type = header

                    if message_type == 4:  # Якщо отримано ACK
                        print(f"Received ACK for fragment {fragment_number + 1}")
                        del self.window[fragment_number]  # Видаляємо фрагмент з вікна
                        if fragment_number == self.base:
                            self.base += 1  # Зсуваємо вікно

                    fragment_data = data[HEADER_LENGTH:]  # Відокремлюємо дані фрагмента
                    if len(received_fragments) == 0:
                        start_time = time.time()
                    if message_type == 2:
                        break

                    if message_type == 3:
                        file_name = fragment_data.decode('utf-8')
                        continue

                    if message_type == 1:  # Прийом файлу
                        # Якщо фрагмент у правильному порядку
                        if fragment_number == expected_seq_num:
                            received_fragments[fragment_number] = fragment_data
                            expected_seq_num += 1

                            # Перевірка буферу для непослідовних фрагментів
                            while expected_seq_num in window:
                                received_fragments[expected_seq_num] = window.pop(expected_seq_num)
                                expected_seq_num += 1
                        elif fragment_number > expected_seq_num:
                            window[fragment_number] = fragment_data

                        # Відправляємо ACK для фрагмента
                        ack_header = self.make_header(fragment_number, total_fragments, 4)  # 4 для ACK
                        self.send_sock.sendto(ack_header, (self.receiver_ip, self.receiver_port))
                        print(f"Sent ACK for fragment {fragment_number + 1}/{total_fragments}")
                    if message_type == 0:
                        received_fragments[fragment_number] = fragment_data

                    # Якщо всі фрагменти отримані
                    if len(received_fragments) == total_fragments:
                        break
                except socket.timeout:
                    # Повторно відправляємо фрагменти з таймаутом
                    for seq_num in self.window:

                        packet, send_time = self.window[seq_num]
                        if time.time() - send_time > 3:  # Таймаут для повторної відправки
                            print(f"Timeout for fragment {seq_num + 1}, resending...")
                            self.send_sock.sendto(packet, (CLIENT_SENT_IP, CLIENT_SENT_PORT))

            if not message_type == 2:
                complete_message = b''.join(received_fragments[i] for i in range(total_fragments))

            elapsed_time = time.time() - start_time  # Вимірюємо час передачі
            if message_type == 0:
                print(f"Received file of size: {len(complete_message)} bytes in {elapsed_time:.5f} seconds.")
                print(f"Received message: {complete_message.decode('utf-8', errors='ignore')}")
                if complete_message.decode('utf-8') == 'quit':
                    print("Received quit signal, closing connection.")
                    self.running = False
                    self.connected = False
                    self.close()
                    break
            elif message_type == 1:
                self.save_file(complete_message, file_name)
                print(f"Received file of size: {len(complete_message)} bytes in {elapsed_time:.5f} seconds.")
            elif message_type == 2 and not self.connected:
                self.connected = True
                self.send_handshake()

    def save_file(self, file_data, file_name):
        save_directory = SAVE_DIRECTORY

        if not os.path.exists(save_directory):
            os.makedirs(save_directory)

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
                print("Failed to connect to a user ..")
                continue

            if message == '1':
                self.choose_file_and_send()
                continue
            if message == 'quit':
                self.connected = False

            message_bytes = message.encode('utf-8')
            total_length = len(message_bytes)

            num_fragments = (total_length // (MAX_UDP_SIZE - HEADER_LENGTH)) + 1
            print(f"Total size: {total_length} bytes")
            print(f"Number of fragments: {num_fragments}")
            for i in range(num_fragments):
                start = i * (MAX_UDP_SIZE - HEADER_LENGTH)
                end = min(start + (MAX_UDP_SIZE - HEADER_LENGTH), total_length)
                fragment = message_bytes[start:end]

                header = self.make_header(i, num_fragments, 0)
                packet = header + fragment
                self.send_sock.sendto(packet, (CLIENT_SENT_IP, CLIENT_SENT_PORT))
                print(f"Sent fragment {i + 1}/{num_fragments}: {len(fragment)} bytes")

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
            name_file = os.path.basename(file_path).encode('utf-8')
            print(f"File Name: {name_file.decode('utf-8')}")
            print(f"Total Size: {total_length} bytes")

            name_header = self.make_header(0, 1, 3)
            name_packet = name_header + name_file
            self.send_sock.sendto(name_packet, (CLIENT_SENT_IP, CLIENT_SENT_PORT))

            num_fragments = (total_length // (MAX_UDP_SIZE - HEADER_LENGTH)) + 1


            next_seq_num = 0  # Наступний порядковий номер для відправлення

            while self.base < num_fragments:
                # Відправляємо фрагменти, якщо є місце у вікні
                while next_seq_num < self.base + self.WINDOW_SIZE and next_seq_num < num_fragments:
                    start = next_seq_num * (MAX_UDP_SIZE - HEADER_LENGTH)
                    end = min(start + (MAX_UDP_SIZE - HEADER_LENGTH), total_length)
                    fragment = file_data[start:end]

                    # Створюємо заголовок з порядковим номером
                    header = self.make_header(next_seq_num, num_fragments, 1)
                    packet = header + fragment
                    self.send_sock.sendto(packet, (CLIENT_SENT_IP, CLIENT_SENT_PORT))


                    print(f"Sent fragment {next_seq_num + 1}/{num_fragments}: {len(fragment)} bytes")
                    self.window[next_seq_num] = (packet, time.time())  # Зберігаємо фрагмент і час відправлення
                    next_seq_num += 1

                # Чекаємо на ACK або таймаут
                self.receive_sock.settimeout(3)

    def send_handshake(self):
        packet = self.make_header(0, 1, 2)
        self.send_sock.sendto(packet, (CLIENT_SENT_IP, CLIENT_SENT_PORT))

    def make_header(self, fragment_number, num_fragments, message_type):  # MESSAGE_TYPE_TEXT=0 text,  1 is file
        return struct.pack('!III', fragment_number, num_fragments, message_type)

    def close(self):
        self.receive_sock.close()
        print("Client closed..")


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
