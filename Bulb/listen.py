import socket

def listen_for_bulbs():
    port = 37020
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", port))

    print("[LISTENER] Waiting for smart bulb broadcasts...")
    while True:
        data, addr = sock.recvfrom(1024)
        print(f"[LISTENER] Received from {addr}: {data.decode()}")

if __name__ == "__main__":
    listen_for_bulbs()
