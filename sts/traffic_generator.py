# Copyright 2011-2013 Colin Scott
# Copyright 2011-2013 Andreas Wundsam
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from pox.lib.packet.ethernet import *
from pox.lib.packet.ipv4 import *
from pox.lib.packet.icmp import *
from pox.lib.packet.arp import *
from util.convenience import random_eth_addr, random_ip_addr
from sts.dataplane_traces.trace import DataplaneEvent
import random

from itertools import count

PING_SEQ = count()

class TrafficGenerator (object):
  '''
  Generate sensible randomly generated (openflow) events
  '''
  def __init__(self, random=random.Random()):
    self.random = random
    self.topology = None
    self._packet_generators = {
        "arp_query": self.arp_query,
        "icmp_ping": self.icmp_ping,
        "icmp_flow": self.icmp_ip_flow,
    }
    self.flow = {}

  def set_topology(self, topology):
    self.topology = topology

  def arp_query(self, src_interface, dst_interface, payload_content=None):
    arp_req = arp()
    hw_src = self._choose_eth_addr(src_interface)
    arp_req.hwsrc = hw_src
    arp_req.hwdst = EthAddr(b"\xff\xff\xff\xff\xff\xff")
    arp_req.opcode = arp.REQUEST
    arp_req.protosrc = self._choose_ip_addr(src_interface)
    arp_req.protodst = self._choose_ip_addr(dst_interface)
    ether = ethernet()
    ether.type = ethernet.ARP_TYPE
    ether.dst = EthAddr(b"\xff\xff\xff\xff\xff\xff")
    ether.src = hw_src
    ether.payload = arp_req
    return ether

  def icmp_ping(self, src_interface, dst_interface, payload_content=None, force_request=False):
    ''' Return an ICMP ping packet; if an interface is none, random addresses are used '''
    e = ethernet()
    e.src = self._choose_eth_addr(src_interface)
    e.dst = self._choose_eth_addr(dst_interface)
    e.type = ethernet.IP_TYPE
    i = ipv4()
    i.protocol = ipv4.ICMP_PROTOCOL
    i.srcip = self._choose_ip_addr(src_interface)
    i.dstip = self._choose_ip_addr(dst_interface)
    ping = icmp()
    #if force_request:
    #  ping.type = TYPE_ECHO_REQUEST
    #else:
    #  ping.type = random.choice([TYPE_ECHO_REQUEST, TYPE_ECHO_REPLY])
    ping.type = TYPE_ECHO_REQUEST
    payload = echo()
    payload.seq = PING_SEQ.next()
    if payload_content == "" or payload_content is None:
      payload_content = "Ping" * 12
    #ping.payload = payload_content
    payload.content = payload_content
    ping.payload = payload
    i.payload = ping
    e.payload = i
    return e


  def icmp_ip_flow(self, src_host, src_interface, dst_ip, payload_content=None, force_request=False, num_packets=5):
    """ Send icmp packets from the same src to the same dst in consecutive rounds of the simulation"""

    # If there is a flow pending for this host, send next packet and decrease count
    if src_host in self.flow:
      self.flow[src_host]['num'] -= 1
      packet = self.flow[src_host]['packet']

      if self.flow[src_host]['num'] <= 0:
        del self.flow[src_host]

    # Else generate the packet and setup the flow
    else:
      if num_packets < 1:
        raise RuntimeError("Number of packets has to be grater than 0")

      # First generate the ICMP packet
      packet = self.icmp_ping_ip(src_interface, dst_ip, payload_content, force_request)

      # store packet in dictionary, send them in the next rounds
      self.flow[src_host] = {}
      self.flow[src_host]['num'] = num_packets - 1         # Number of pending sends
      self.flow[src_host]['packet'] = packet               # ICMP ip Packet

    return packet


  def icmp_ping_ip(self, src_interface, dst_IP, payload_content=None, force_request=False):
    ''' Return an ICMP ping packet; if an interface is none, random addresses are used '''
    e = ethernet()
    e.src = self._choose_eth_addr(src_interface)
    e.dst = EthAddr("00:00:00:00:00:11")
    #e.dst = self._choose_eth_addr(dst_interface)
    e.type = ethernet.IP_TYPE
    i = ipv4()
    i.protocol = ipv4.ICMP_PROTOCOL
    i.srcip = self._choose_ip_addr(src_interface)
    i.dstip = dst_IP
    ping = icmp()
    if force_request:
      ping.type = TYPE_ECHO_REQUEST
    else:
      # RM changed random to self.random
      ping.type = self.random.choice([TYPE_ECHO_REQUEST, TYPE_ECHO_REPLY])
    if payload_content == "" or payload_content is None:
      payload_content = "Ping" * 12
    ping.payload = payload_content
    i.payload = ping
    e.payload = i
    return e


  def generate(self, packet_type, src_host=None, dst_host=None,
               send_to_self=False, payload_content=None, force_request=None):
    ''' Generate a packet, return a function to have source host send it, and return the corresponding event '''
    if packet_type not in self._packet_generators:
      raise AttributeError("Unknown event type %s" % str(packet_type))
    if self.topology is None:
      raise RuntimeError("TrafficGenerator needs access to topology")

    (src_host, src_interface) = self._choose_host(src_host, self.topology.hosts)
    if send_to_self:
      (dst_host, dst_interface) = (src_host, src_interface)
    else:
      (dst_host, dst_interface) = self._choose_host(dst_host,
                                      [h for h in self.topology.hosts if h != src_host])

    if force_request is not None:
      packet = self._packet_generators[packet_type](src_interface, dst_interface,
                                                  payload_content=payload_content, 
                                                  force_request=force_request)
    else:
      packet = self._packet_generators[packet_type](src_interface, dst_interface,
                                                  payload_content=payload_content)
    def send():
      src_host.send(src_interface, packet)
    return (DataplaneEvent(src_interface, packet), send)


  def generate_ip(self, packet_type, src_host=None, dst_IP=None,
                  send_to_self=False, payload_content=None, force_request=None, num_packets=5):
    ''' Generate a packet, return a function to have source host send it, and return the corresponding event '''
    if packet_type not in self._packet_generators:
      raise AttributeError("Unknown event type %s" % str(packet_type))
    if self.topology is None:
      raise RuntimeError("TrafficGenerator needs access to topology")

    (src_host, src_interface) = self._choose_host(src_host, self.topology.hosts)
    if send_to_self:
      (dst_host, dst_interface) = (src_host, src_interface)

    if packet_type == 'icmp_flow':
      packet = self.icmp_ip_flow(src_host, src_interface, dst_IP, payload_content=payload_content, num_packets=num_packets)

    else:
      if force_request is not None:
        packet = self.icmp_ping_ip(src_interface, dst_IP, payload_content=payload_content, force_request=force_request)
      else:
        packet = self.icmp_ping_ip(src_interface, dst_IP, payload_content=payload_content)

    def send():
      src_host.send(src_interface, packet)
    return (DataplaneEvent(src_interface, packet), send)

  def _choose_host(self, host, hosts):
    '''
    Validate the existence of a host and its interfaces;
    if host is None, choose randomly from hosts
    '''
    if host is None:
      if len(hosts) == 0:
        raise RuntimeError("No host to choose from!")
      host = self.random.choice(hosts)
    if host in self.topology.hid2host.keys():
      host = self.topology.hid2host[host]
    if host not in self.topology.hosts:
      raise RuntimeError("Unknown host: %s" % (str(host)))
    if len(host.interfaces) == 0:
      raise RuntimeError("No interfaces to choose from on host %s!" % (str(host)))
    interface = self.random.choice(host.interfaces)
    return (host, interface)

  def _choose_eth_addr(self, interface):
    if interface is not None:
      return interface.hw_addr
    else:
      return random_eth_addr()

  def _choose_ip_addr(self, interface):
    if interface is not None and hasattr(interface, 'ips'):
      return self.random.choice(interface.ips)
    else:
      return random_ip_addr()

