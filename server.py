import socket
import threading
import struct

from tkinter import Tk
from tkinter import filedialog
import time

import os

MAX_UDP_SIZE = 1472
HEADER_LENGTH=14
SAVE_DIRECTORY='/Users/ulian/PycharmProjects/pksPraktika/receive'


CLIENT_MY_IP = "127.0.0.1"
CLIENT_MY_PORT = 50602

CLIENT_SENT_IP = "127.0.0.1"
CLIENT_SENT_PORT = 50601

# CLIENT_MY_IP = None
# CLIENT_MY_PORT = None
# CLIENT_SENT_IP = None
# CLIENT_SENT_PORT = None

class Client2:
    WINDOW_SIZE = 4

    def __init__(self, ip, port, receiver_ip, receiver_port):
        self.receive_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.receiver_ip = receiver_ip
        self.receiver_port = receiver_port
        self.receive_sock.bind((ip, port))
        self.running = True
        self.connected = False

        self.receive_thread = threading.Thread(target=self.receive)
        self.receive_thread.daemon = True
        self.receive_thread.start()

        self.window = {}
        self.base = 0

        self.keep_alive_interval = 5
        self.heartbeat_timeout = 3
        self.heartbeat_sent_count = 0
        self.last_heartbeat_time = time.time()
        self.heartbeat_thread = threading.Thread(target=self.send_heartbeats)
        self.heartbeat_thread.daemon = True
        self.heartbeat_thread.start()

    def send_heartbeats(self):
        while self.running:
            time.sleep(self.keep_alive_interval)
            if not self.connected:
                continue

            current_time = time.time()
            if current_time - self.last_heartbeat_time >= self.keep_alive_interval:
                heartbeat_header = self.make_header(0, 1, 5, 0)  # 5  heartbeat
                self.send_sock.sendto(heartbeat_header, (self.receiver_ip, self.receiver_port))
                self.heartbeat_sent_count += 1

                if self.heartbeat_sent_count >= self.heartbeat_timeout:
                    print("The connection is lost. No response to heartbeat.")
                    self.running = False
                    self.close()

    def receive(self):
        while self.running:
            received_fragments = {}
            file_name = None

            expected_seq_num = 0
            window = {}
            ###=======================================for receive=======================================####
            while True:
                try:
                    data, addr = self.receive_sock.recvfrom(MAX_UDP_SIZE)
                    header = struct.unpack('!IIIH', data[:HEADER_LENGTH])

                    fragment_number, total_fragments, message_type, crc_received = header
                    crc_calculated = self.crc16(data[HEADER_LENGTH:])

                    if crc_calculated != crc_received and message_type in {0 , 1}:
                        print(
                            f"Received fragment {fragment_number + 1} with CRC error. Expected: {crc_received}, Calculated: {crc_calculated}")
                        continue
                    elif message_type in {0 , 1}:
                        # print(f"Received fragment {fragment_number + 1} without CRC error. Expected: {crc_received}, Calculated: {crc_calculated}")
                        pass

                    if message_type == 4:
                        print(f"Received ACK for fragment {fragment_number + 1}")
                        del self.window[fragment_number]
                        if fragment_number == self.base:
                            self.base += 1

                    if message_type == 6:  # 6 heartbeat reply
                        # print("Received a response to heartbeat.")
                        self.last_heartbeat_time = time.time()
                        self.heartbeat_sent_count = 0
                        continue
                    if message_type == 5:  # 5  heartbeat
                        # print("Received heartbeat.")
                        self.last_heartbeat_time = time.time()
                        self.heartbeat_sent_count = 0

                        heartbeat_header = self.make_header(0, 1, 6, 0)  # 5  heartbeat
                        self.send_sock.sendto(heartbeat_header, (self.receiver_ip, self.receiver_port))

                        continue

                    fragment_data = data[HEADER_LENGTH:]
                    if len(received_fragments) == 0:
                        start_time = time.time()
                    if message_type == 2:  # handshake
                        break

                    if message_type == 3:  # NAME FILE
                        file_name = fragment_data.decode('utf-8')
                        continue

                    if message_type in {0 , 1}:  # FILE or TEXT
                        if fragment_number == expected_seq_num:
                            received_fragments[fragment_number] = fragment_data
                            expected_seq_num += 1

                            while expected_seq_num in window:
                                received_fragments[expected_seq_num] = window.pop(expected_seq_num)
                                expected_seq_num += 1
                        elif fragment_number > expected_seq_num:
                            window[fragment_number] = fragment_data

                        ack_header = self.make_header(fragment_number, total_fragments, 4, 0)  # 4  ACK
                        self.send_sock.sendto(ack_header, (self.receiver_ip, self.receiver_port))
                        print(f"Sent ACK for fragment {fragment_number + 1}/{total_fragments}")
                    # if message_type == 0:  # TEXT
                    #     received_fragments[fragment_number] = fragment_data

                    if len(received_fragments) == total_fragments:
                        break
                except socket.timeout:

                    for seq_num in self.window:

                        packet, send_time = self.window[seq_num]
                        if time.time() - send_time > 3:
                            print(f"Timeout for fragment {seq_num + 1}, resending...")
                            self.send_sock.sendto(packet, (CLIENT_SENT_IP, CLIENT_SENT_PORT))
                except Exception as e:
                    self.running = False
                    self.connected = False
                    break
                ###==================================================================================####
            if message_type in {0, 1, 3}:
                complete_message = b''.join(received_fragments[i] for i in range(total_fragments))

            elapsed_time = time.time() - start_time
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
            try:
                message = input("Input message to server (or '1' to send a file):  ")
                if self.running == False:
                    break
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
                    self.running = False

                message_bytes = message.encode('utf-8')
                total_length = len(message_bytes)

                num_fragments = (total_length // (MAX_UDP_SIZE - HEADER_LENGTH)) + 1
                print(f"Total size: {total_length} bytes")
                print(f"Number of fragments: {num_fragments}")

                self.SelectRepeat(num_fragments, message_bytes, total_length, 0)
            except OSError as e:
                print(f"Error sending packet: {e}")
                self.running = False
            except Exception as e:
                print(f"Error during receiving: {e}")
                self.running = False

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

            name_header = self.make_header(0, 1, 3, 0)
            name_packet = name_header + name_file
            self.send_sock.sendto(name_packet, (CLIENT_SENT_IP, CLIENT_SENT_PORT))

            num_fragments = (total_length // (MAX_UDP_SIZE - HEADER_LENGTH)) + 1

            self.SelectRepeat(num_fragments,file_data,total_length,1)


    def SelectRepeat(self,num_fragments,file_data,total_length,message_type):
        next_seq_num = 0
        while self.base < num_fragments:
            while next_seq_num < self.base + self.WINDOW_SIZE and next_seq_num < num_fragments:
                start = next_seq_num * (MAX_UDP_SIZE - HEADER_LENGTH)
                end = min(start + (MAX_UDP_SIZE - HEADER_LENGTH), total_length)
                fragment = file_data[start:end]

                crc = self.crc16(fragment)

                header = self.make_header(next_seq_num, num_fragments, message_type, crc)
                packet = header + fragment
                self.send_sock.sendto(packet, (CLIENT_SENT_IP, CLIENT_SENT_PORT))

                print(f"Sent fragment {next_seq_num + 1}/{num_fragments}: {len(fragment)} bytes")
                self.window[next_seq_num] = (packet, time.time())
                next_seq_num += 1

            self.receive_sock.settimeout(3)
        self.base=0

    def crc16(self, data: bytes) -> int:
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        return crc

    def send_handshake(self):
        packet = self.make_header(0, 1, 2, 0)
        self.send_sock.sendto(packet, (CLIENT_SENT_IP, CLIENT_SENT_PORT))

    ###=======I — unsigned int, 4 ₴₴ H=2bite ₴₴ B=1bite ₴₴ Q=8bite ==========###
    def make_header(self, fragment_number, num_fragments, message_type, crc):
        return struct.pack('!IIIH', fragment_number, num_fragments, message_type, crc)

    def close(self):
        print("Closing connection...")
        self.running = False
        self.receive_sock.close()
        self.send_sock.close()
        # self.receive_thread.join()
        print("Connection closed.")


if __name__ == "__main__":
    # print("!!!do not forget to change the path where to save the received files in the parameters!!!");
    #
    # CLIENT_MY_PORT = int(input("Enter your source port: "))
    # CLIENT_SENT_PORT = int(input("Enter destination port: "))
    # CLIENT_SENT_IP = input("Enter destination IP: ")
    # CLIENT_MY_IP = input("Enter your IP: ")

    client = Client2(CLIENT_MY_IP, CLIENT_MY_PORT, CLIENT_SENT_IP, CLIENT_SENT_PORT)

    client.send()

    client.close()