import os
import requests
import socket
import time

#Keep alive / ARP

def send_arp(router_ip="192.168.0.1"):
    while True:
        print(f"[ARP] sending ARP to {router_ip}")
        os.system(f"arping -c 1 {router_ip}")
        time.sleep(30)

#Heartbeat

def heartbeat(cloud_ip="172.18.106.184"):
    while True:
        try:
            print("[HEARTBEAT] Sending to cloud...")
            requests.post(f"https://{cloud_ip}:6000/heartbeat", json={"status": "alive"}, verify=False)
        except Exception as e:
            print(f"[HEARTBEAT] Failed: {e}")
        time.sleep(60)

#Discovery

def network_discovery():
    discovery_message = "SMARTBULB_DISCOVERY"
    broadcast_ip = "255.255.255.255"
    port = 37020

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    while True:
        print(f"[DISCOVERY] Broadcasting '{discovery_message}' to {broadcast_ip}:{port}")
        sock.sendto(discovery_message.encode(), (broadcast_ip, port))
        time.sleep(20)
