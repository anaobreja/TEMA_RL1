#!/usr/bin/python3
import binascii
import sys
import struct
import wrapper
import threading
import time
from wrapper import recv_from_any_link, send_to_link, get_switch_mac, get_interface_name

mac_table = {}
vlan_table = {}

own_bridge_id = None
root_bridge_id = None
root_path_cost = 0
root_port = None
trunk_ports = []
port_states = {} 

def parse_ethernet_header(data):
    dest_mac = data[0:6]
    src_mac = data[6:12]
    ether_type = (data[12] << 8) + data[13]

    vlan_id = -1
    if ether_type == 0x8200:
        vlan_tci = int.from_bytes(data[14:16], byteorder='big')
        vlan_id = vlan_tci & 0x0FFF
        ether_type = (data[16] << 8) + data[17]

    return dest_mac, src_mac, ether_type, vlan_id

def create_vlan_tag(vlan_id):
    return struct.pack('!H', 0x8200) + struct.pack('!H', vlan_id & 0x0FFF)

def send_bpdu():
    global own_bridge_id, root_bridge_id, trunk_ports
    while True:
        if own_bridge_id == root_bridge_id:
            for port in trunk_ports:
                bpdu_frame = create_bpdu_frame()
                send_to_link(port, len(bpdu_frame), bpdu_frame)
        time.sleep(1)

def create_bpdu_frame():
    global root_bridge_id, root_path_cost, own_bridge_id

    dest_mac =  binascii.unhexlify("01:80:c2:00:00:00".replace(':', ''))
    macs = dest_mac + get_switch_mac()
    llc = struct.pack("!H3b", 38, 0x42, 0x42, 0x03)
    bpdu = bytes(5) + struct.pack("!QIQ", root_bridge_id, root_path_cost, own_bridge_id) + bytes(10)

    data = macs + llc + bpdu

    return data

def is_unicast(mac_address):
    first_byte = int(mac_address.split(":")[0], 16)
    return (first_byte & 1) == 0

def process_bpdu(interface, data):
    global root_bridge_id, root_path_cost, root_port, own_bridge_id, port_states


    bpdu_root_id, bpdu_sender_path_cost, bpdu_sender_bridge_id = struct.unpack("!QIQ", data[22:42])

    if bpdu_root_id < root_bridge_id:

        last_root_bridge_id = root_bridge_id
        root_path_cost = bpdu_sender_path_cost + 10
        root_port = interface
        root_bridge_id = bpdu_root_id
    
        if own_bridge_id == last_root_bridge_id:
            for port in trunk_ports:
                if port != root_port:
                    port_states[port] = "BLOCKING"

        if port_states[root_port] == "BLOCKING":
            port_states[root_port] = "FORWARDING"

        for port in trunk_ports:
            if port != root_port:
                bpdu_frame = create_bpdu_frame()
                send_to_link(port, len(bpdu_frame), bpdu_frame)

    elif bpdu_root_id == root_bridge_id:
        if interface == root_port and bpdu_sender_path_cost + 10 < root_path_cost:
            root_path_cost = bpdu_sender_path_cost + 10
        elif interface != root_port:
            if bpdu_sender_path_cost > root_path_cost:
                port_states[interface] = "FORWARDING"

    elif bpdu_sender_bridge_id == own_bridge_id:
        port_states[interface] = "BLOCKING"

    if own_bridge_id == root_bridge_id:
        for port in port_states:
            port_states[port] = "FORWARDING"


def read_configs(switch_id):
    global own_bridge_id, root_bridge_id, root_path_cost, trunk_ports, port_states
    file_name = f"configs/switch{switch_id}.cfg"
    with open(file_name, 'r') as file:
        lines = file.readlines()
        priority = int(lines[0].strip())

        for i, line in enumerate(lines[1:]):
            line = line.strip()
            if line and line[-1] == 'T':
                trunk_ports.append(i)
                vlan_table[i] = -1
                port_states[i] = "BLOCKING" 
            else:
                vlan_table[i] = int(line[-1])
                port_states[i] = "FORWARDING"
    
    own_bridge_id = priority
    root_bridge_id = own_bridge_id
    root_path_cost = 0

    if own_bridge_id == root_bridge_id:
        for port in trunk_ports:
            port_states[port] = "FORWARDING"



def main():
    if len(sys.argv) < 2:
        print("Usage: python3 script.py <switch_id> [<interface_config>...]")
        return

    switch_id = sys.argv[1]
    num_interfaces = wrapper.init(sys.argv[2:])
    interfaces = range(num_interfaces)

    print(f"# Starting switch with id {switch_id}", flush=True)
    print("[INFO] Switch MAC", ':'.join(f'{b:02x}' for b in get_switch_mac()))

    read_configs(switch_id)

    t = threading.Thread(target=send_bpdu)
    t.start()

    while True:
        interface, data, length = recv_from_any_link()
        dest_mac, src_mac, ethertype, vlan_id = parse_ethernet_header(data)

        dest_mac = ':'.join(f'{b:02x}' for b in dest_mac)
        src_mac = ':'.join(f'{b:02x}' for b in src_mac)

        if dest_mac == "01:80:c2:00:00:00":
            process_bpdu(interface, data)
            continue

        mac_table[src_mac] = interface

        if vlan_id == -1:
            vlan = vlan_table.get(interface, -1)
        else:
            vlan = vlan_id
            length -= 4
            data = data[0:12] + data[16:]

        if is_unicast(dest_mac):
            if dest_mac in mac_table:
                out_interface = mac_table[dest_mac]
                if vlan_table[out_interface] != vlan:
                    tagged_frame = data[0:12] + create_vlan_tag(vlan) + data[12:]
                    send_to_link(out_interface, length + 4, tagged_frame)
                    send_to_link(out_interface, length, data)
                else:
                    send_to_link(out_interface, length, data)
            else:
                for i in interfaces:
                    if i != interface and port_states.get(i) == "FORWARDING":
                        if vlan_table[i] != vlan:
                            tagged_frame = data[0:12] + create_vlan_tag(vlan) + data[12:]
                            send_to_link(i, length + 4, tagged_frame)
                        else:
                            send_to_link(i, length, data)
        else:
            for i in interfaces:
                if i != interface and port_states.get(i) == "FORWARDING":
                    if vlan_table[i] != vlan:
                        tagged_frame = data[0:12] + create_vlan_tag(vlan) + data[12:]
                        send_to_link(i, length + 4, tagged_frame)
                        send_to_link(i, length, data)
                    else:
                        send_to_link(i, length, data)

if __name__ == "__main__":
    main()
