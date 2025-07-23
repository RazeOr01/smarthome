import sys
print("Interpreter use is  :", sys.executable)

import sys
import argparse
import logging
from scapy.all import sniff
from river.anomaly import HalfSpaceTrees
from collections import deque

# ---------------------------- Logging ----------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

# ---------------------------- Feature Extraction ----------------------------
def extract_features(packet):
    try:
        if packet.haslayer("IP"):
            src_ip = packet["IP"].src
            dst_ip = packet["IP"].dst
            packet_size = len(packet)
            protocol = packet["IP"].proto

            # Hash IPs to numeric values for use in anomaly detection
            return {
                "src_ip": hash(src_ip) % 10000,      # Convert to int
                "dst_ip": hash(dst_ip) % 10000,      # Convert to int
                "packet_size": float(packet_size),
                "protocol": float(protocol)
            }
    except Exception as e:
        logging.warning(f"Packet parsing failed: {e}")
    return None
# ---------------------------- Packet Handler ----------------------------
def process_packet(packet):
    features = extract_features(packet)
    if features:
        logging.info(
            f"Dst: {features['dst_ip']}, Features: {features}"
        )

# ---------------------------- Sniffing ----------------------------
def monitor_traffic(interface: str, target_ip: str):
    logging.info(f"Sniffing on {interface} for IP {target_ip}")
    sniff(
        iface=interface,
        prn=process_packet,
        store=False,
        filter=f"host {target_ip}"  # BPF filter to limit traffic
    )

# ---------------------------- Main Entry ----------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Online anomaly detector for a target IP.")
    parser.add_argument("ip", help="Target IP address to monitor (e.g. 192.168.0.10)")
    parser.add_argument("--interface", default="wlo1", help="Network interface (default: wlan0)")
    args = parser.parse_args()

    try:
        monitor_traffic(interface=args.interface, target_ip=args.ip)
    except KeyboardInterrupt:
        logging.info("Monitoring stopped by user.")

