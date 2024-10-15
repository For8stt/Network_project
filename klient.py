import socket
import threading
import struct


MAX_UDP_SIZE = 65507

CLIENT_MY_IP = "127.0.0.1"
CLIENT_MY_PORT = 50602

CLIENT_SENT_IP = "127.0.0.1"
CLIENT_SENT_PORT = 50601

class Client:
    def __init__(self, ip, port, receiver_ip, receiver_port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP socket creation
        self.receiver_ip = receiver_ip
        self.receiver_port = receiver_port
        self.sock.bind((ip, port))  # Bind to IP and port
        self.running = True

    def receive(self):
        while self.running:

            # data, self.receiver = self.sock.recvfrom(1024)  # Receive data
            # print(f"Received message: {data.decode('utf-8')}")
            received_fragments = {}
            while True:
                data, addr = self.sock.recvfrom(65535)  # Розмір пакета
                header = struct.unpack('!II', data[:8])  # Розпакування заголовка
                fragment_number, total_fragments = header
                fragment_data = data[8:]  # Відокремлюємо дані фрагмента

                received_fragments[fragment_number] = fragment_data
                print(f"Received fragment {fragment_number + 1}/{total_fragments}: {fragment_data.decode('utf-8')}")

                # Якщо всі фрагменти отримані
                if len(received_fragments) == total_fragments:
                    break

            complete_message = b''.join(received_fragments[i] for i in range(total_fragments))
            print(f"Received message: {complete_message.decode('utf-8')}")

            if data.decode('utf-8') == "quit":
                print("Client disconnected. Closing server.")
                self.running = False
                break

    def send(self):
        while self.running:
            message = input("Input message to server: ")

            if message == "quit":
                print("Closing connection with server.")
                self.running = False
                break

            message_bytes = message.encode('utf-8')
            total_length = len(message_bytes)

            num_fragments = (total_length // (MAX_UDP_SIZE - 8))+1

            for i in range(num_fragments):
                start = i * (MAX_UDP_SIZE - 8)
                end = min(start + (MAX_UDP_SIZE - 8), total_length)
                fragment = message_bytes[start:end]

                header = struct.pack('!II', i, num_fragments)
                packet = header + fragment
                self.sock.sendto(packet, (CLIENT_SENT_IP, CLIENT_SENT_PORT))
                print(f"Sent fragment {i + 1}/{num_fragments}: {fragment.decode('utf-8')}")

    def close(self):
        self.sock.close()
        print("Client closed..")

if __name__ == "__main__":
    client = Client(CLIENT_MY_IP, CLIENT_MY_PORT, CLIENT_SENT_IP, CLIENT_SENT_PORT)

    # Start threads for sending and receiving
    receive_thread = threading.Thread(target=client.receive)
    send_thread = threading.Thread(target=client.send)

    receive_thread.start()
    send_thread.start()

    receive_thread.join()
    send_thread.join()

    client.close()
