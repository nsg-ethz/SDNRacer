# Copyright 2011-2013 Colin Scott
# Copyright 2012-2013 Sam Whitlock
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

'''
Utility functions for launching network namespaces.
'''

from pox.lib.addresses import EthAddr, IPAddr

import subprocess
import struct
import fcntl
import socket
import os
from exceptions import EnvironmentError
from platform import system
import Queue
import logging
log = logging.getLogger("netns")

ETH_P_ALL = 3                     # from linux/if_ether.h

def launch_namespace(cmd, guest_ip_addr_str, iface_number, prefix_length=24,
                     host_ip_addr_str="", guest_hw_addr=None, cwd=None,
                     env=None):
  '''
  Set up and launch cmd in a new network namespace.

  Returns a pair:
   (raw socket bound to host veth interface,
    Popen object for communicating with guest namespace)

  This method uses functionality that requires CAP_NET_ADMIN capabilites. This
  means that the calling method should check that the python process was
  launched as admin/superuser.

  Parameters:
    - cmd: the string to launch, in a separate namespace
    - ip_addr_str: the ip address to assign to the namespace's interace.
                   Must be a string! not a IPAddr object
    - iface_number: unique integer for the namespace and host virtual interfaces.
    - guest_hw_addr: mac address for the guest (auto generated if None)
  '''
  if system() != 'Linux':
    raise EnvironmentError('network namespace functionality requires a Linux environment')

  uid = os.geteuid()
  if uid != 0:
    # user must have CAP_NET_ADMIN, which doesn't have to be su, but most often is
    raise EnvironmentError("superuser privileges required to launch network namespace")

  host_device = "heth%s" % str(iface_number)
  guest_device = "geth%s" % str(iface_number)

  try:
    # Clean up previous network namespaces
    # (Delete the device if it already exists)
    with open(os.devnull, 'wb') as null:
      for dev in (host_device, guest_device):
        if subprocess.call(['ip', 'link', 'show', dev], stdout=null, stderr=null) == 0:
          subprocess.check_call(['ip', 'link', 'del', dev])

    # create a veth pair and set the host end to be promiscuous
    add_cmd = ['ip','link','add','name',host_device,'type','veth','peer',
               'name',guest_device]
    if guest_hw_addr:
      guest_hw_addr = EthAddr(guest_hw_addr)
      add_cmd.append('address')
      add_cmd.append(guest_hw_addr.toStr())
    subprocess.check_call(add_cmd)
    guest_eth_addr = get_eth_address_for_interface(guest_device)
    log.debug("Guest ETH %s" % guest_eth_addr)
    host_eth_addr = get_eth_address_for_interface(host_device)
    log.debug("Host ETH %s" % host_eth_addr)

    subprocess.check_call(['ip','link','set',host_device,'promisc','on'])
    # Our end of the veth pair
    subprocess.check_call(['ip','link','set',host_device,'up'])
    if host_ip_addr_str != "":
      # Set a host IP on the same subnet as the guest so that host sockets automatically get
      # bound to the correct virtual interface.
      subprocess.check_call(['ip', 'addr', 'add', "%s/%d" % (host_ip_addr_str, prefix_length), 'dev', host_device])
  except subprocess.CalledProcessError:
    raise # TODO raise a more informative exception


  # all else should have succeeded, so now we fork and unshare for the guest
  # TODO(cs): use popen_filtered here?
  guest = subprocess.Popen(["unshare", "-n", "--", "/bin/bash"],
                           stdin=subprocess.PIPE, env=env, cwd=cwd)

  # push down the guest device into the netns
  try:
    subprocess.check_call(['ip', 'link', 'set', guest_device, 'netns', str(guest.pid)])
  except subprocess.CalledProcessError:
    raise # TODO raise a more informative exception

  # Bring up the interface on the guest.
  guest.stdin.write("ip link set %s up\n" % guest_device)
  # Set the IP address of the virtual interface. Note that this has the nice
  # side effect that the host can open sockets to the IP address (since the
  # guest will begin responding to ARPs).
  guest.stdin.write("ip addr add %s/%d dev %s\n" % (guest_ip_addr_str, prefix_length, guest_device))

  # Send the command.
  guest.stdin.write(cmd + "\n")

  return (guest, guest_eth_addr, host_device)

# TODO(cs): move these functions -- not necessarily specific to network
# namespaces.
def bind_raw_socket(host_device, blocking=0):
  # make the host-side (STS-side) socket
  # do this before unshare/fork to make failure/cleanup easier
  # Make sure we aren't monkeypatched first:
  if hasattr(socket, "_old_socket"):
    raise RuntimeError("MonkeyPatched socket! Bailing")
  s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, ETH_P_ALL)
  # Make sure the buffers are big enough to fit at least one full ethernet
  # packet
  s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8192)
  s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 8192)
  s.bind((host_device, ETH_P_ALL))
  s.setblocking(blocking)
  return s

# TODO(cs): pcap is an awkward way to filter out OpenFlow for the
# intracontroller patch panel. A cleaner, simpler way would be to
# create a separate veth pair for OpenFlow/sync, in addition to the
# veth pair for intracontroller communication.
def bind_pcap(host_device, filter_string=None):
  '''
   - host_device: interface to bind to.
   - filter_string: tcp dump syntax packet filter.

  Returns a BufferedPCap object that queues all packets read on the PCap.

  Note that this method spawns a new thread! This will certainly be
  changed in the future to run as an io_worker in io_master.
  '''
  return BufferedPCap(host_device, filter_string)

class BufferedPCap(object):
  ''' Thread-safe PCap wrapper that buffers all incoming packets in a
  thread-safe queue. '''
  def __init__(self, host_device, filter_string):
    self.read_queue = Queue.Queue()
    import pox.lib.pxpcap as pxpcap
    if not pxpcap.enabled:
      raise RuntimeError('''You need to compile POX's pxpcap library:\n'''
                         '''$ (cd pox/pox/lib/pxcap/pxcap_c && python setup.py build)''')
    pcap = pxpcap.PCap(start=False, filter=filter_string,
                       callback=self._pcap_callback)
    pcap.open(device=host_device, promiscuous=True)
    pcap.start(addListeners=False)
    self._pcap = pcap

  def _pcap_callback(self, pcap, data, sec, usec, length):
    self.read_queue.put(data)

  def inject(self, data):
    # TODO(cs): Murphy believes this is a non-blocking, but is not entirely
    # sure... should double check.
    self._pcap.inject(data)

  def close(self):
    self._pcap.close()

  @property
  def pcap(self):
    return self._pcap

def get_eth_address_for_interface(ifname):
  '''Returns an EthAddr object from the interface specified by the argument.

  interface is a string, commonly eth0, wlan0, lo.'''
  s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  info = fcntl.ioctl(s.fileno(), 0x8927,  struct.pack('256s', ifname[:15]))
  s.close()
  return EthAddr(''.join(['%02x:' % ord(char) for char in info[18:24]])[:-1])

