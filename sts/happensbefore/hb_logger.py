from _collections import defaultdict
from threading import RLock
import itertools
import logging
import time
import base64
import copy

from pox.lib.revent.revent import EventMixin
from sts.happensbefore.hb_sts_events import *
from sts.happensbefore.hb_tags import ObjectRegistry
from sts.happensbefore.hb_events import *
from pox.openflow.libopenflow_01 import *
from sts.util.convenience import base64_encode_raw, base64_decode, base64_decode_openflow
from sts.util.procutils import prefixThreadOutputMatcher, PrefixThreadLineMatch
from sts.happensbefore.hb_graph import HappensBeforeGraph

class HappensBeforeLogger(EventMixin):
  '''
  Listens to and logs the following events:
  - Data plane:
   * receive dataplane (switches)
   * receive dataplane (hosts)
   * send dataplane (hosts+switches)
  - Control plane:
   * receive Openflow msgs (controller to switch)
   * send Openflow msgs (switch to controller)
  - Switch:
   * internal processing
  
  Logs the following operations:
   * Flow table read
   * Flow table touch
   * Flow table modify
   '''
  
  controller_hb_msg_in = "HappensBefore-MessageIn"
  controller_hb_msg_out = "HappensBefore-MessageOut"
  
  def __init__(self, patch_panel):
    self.log = logging.getLogger("hb_logger")
    # TODO(jm): a regular (non reentrant) lock would suffice here
    self.reentrantlock = RLock()

    self.output = None
    self.output_path = ""
    self.patch_panel = patch_panel
    
    # State for linking of events
    self.pids = ObjectRegistry() # packet obj -> pid
    self.mids = ObjectRegistry() # message obj -> mid
    self.buffer_pids = defaultdict(dict) # dpid -> [buffer_id -> pid]
    self.started_regular_switch_event = dict() # dpid -> event
    self.started_async_switch_event = dict() # dpid -> event
    self.started_host_event = dict() # hid -> event
    self.explicit_successors_regular_switch_event = defaultdict(list) # dpid -> [event]
    self.explicit_successors_async_switch_event = defaultdict(list) # dpid -> [event]
    self.explicit_successors_host_event = defaultdict(list) # hid -> [event]
    self.pending_packet_update = dict() # dpid -> packet
    
    self.msg_to_rxbase64 = dict()
    
    # State for linking of controller events
    self.unmatched_HbMessageSend = defaultdict(list) # dpid -> []
    self.unmatched_HbMessageHandle = defaultdict(list) # dpid -> []
    
    self.unmatched_controller_lines = [] # lines
    self.controller_packetin_to_mid_out = dict() # (swid, b64msg) -> mid_out
    self.controller_packetin_mid_out_to_HbControllerHandle = dict() # mid_out -> HbControllerHandle
    self.controller_packetin_mid_out_to_temporary_tag = dict() # mid_out -> HbControllerHandle
    
    self.decoded_msg_to_rxbase64 = dict()
    self.decoded_line_msg = dict()
    
    prefixThreadOutputMatcher.add_string_to_match(self.controller_hb_msg_in)
    prefixThreadOutputMatcher.add_string_to_match(self.controller_hb_msg_out)
    prefixThreadOutputMatcher.addListener(PrefixThreadLineMatch, self.handle_no_exceptions)

    self._subscribe_to_PatchPanel(patch_panel)
    
  def open(self, results_dir=None, output_filename="hb.json"):
    '''
    Start a trace
    '''
    if results_dir is not None:
      self.output_path = results_dir + "/" + output_filename
    else:
      raise ValueError("Default results_dir currently not supported")
    self.output = open(self.output_path, 'w')
    
  def close(self):
    '''
    End a trace
    '''
    # Flush the log
    if self.output is not None and not self.output.closed:
      self.output.close()
    self.output = None

  
  def write(self,msg):
#     self.log.info(msg)
    if self.output is not None and not self.output.closed:
      self.output.write(str(msg) + '\n')
      self.output.flush()
    else:
       raise Exception("Not opened -- call HappensBeforeLogger.open()")
  
  def handle_no_exceptions(self, event):
    """ Handle event, catch exceptions before they go back to STS/POX
    """
    with self.reentrantlock: # this is possibly multithreaded
      try:
        if self.output is not None:
          event_handlers = {
              TraceHostPacketHandleBegin: self.handle_host_ph_begin,
              TraceHostPacketHandleEnd: self.handle_host_ph_end,
              TraceHostPacketSend: self.handle_host_ps,
              TraceAsyncSwitchFlowExpiryBegin: self.handle_async_switch_fexp_begin,
              TraceAsyncSwitchFlowExpiryEnd: self.handle_async_switch_fexp_end,
              TraceSwitchPacketHandleBegin: self.handle_switch_ph_begin,
              TraceSwitchPacketHandleEnd: self.handle_switch_ph_end,
              TraceSwitchMessageHandleBegin: self.handle_switch_mh_begin,
              TraceSwitchMessageHandleEnd: self.handle_switch_mh_end,
              TraceSwitchMessageSend: self.handle_switch_ms,
              TraceSwitchPacketSend: self.handle_switch_ps,
              TraceSwitchMessageRx: self.handle_switch_rx_wire,
              TraceSwitchMessageTx: self.handle_switch_tx_wire,
              TraceSwitchFlowTableRead: self.handle_switch_table_read,
              TraceSwitchFlowTableWrite: self.handle_switch_table_write,
              TraceSwitchFlowTableEntryExpiry: self.handle_switch_table_entry_expiry,
              TraceSwitchPacketDrop: self.handle_switch_packet_drop,
              TraceSwitchBufferPut: self.handle_switch_buf_put,
              TraceSwitchBufferGet: self.handle_switch_buf_get,
              TraceSwitchPacketUpdateBegin: self.handle_switch_pu_begin,
              TraceSwitchPacketUpdateEnd: self.handle_switch_pu_end,
              PrefixThreadLineMatch: self._handle_line_match
          }
          handler = None
          if type(event) in event_handlers:
            handler = event_handlers[type(event)]
            handler(event)
      except Exception as e:
        # NOTE JM: do not remove, otherwise exceptions get swallowed by STS
        import traceback
        traceback.print_exc()
        pass # set a breakpoint here
  
  def subscribe_to_DeferredOFConnection(self, connection):
    connection.addListener(TraceSwitchMessageTx, self.handle_no_exceptions)
    connection.addListener(TraceSwitchMessageSend, self.handle_no_exceptions)
      
  def _subscribe_to_PatchPanel(self, patch_panel):
    for host in patch_panel.hosts:
      host.addListener(TraceHostPacketHandleBegin, self.handle_no_exceptions)
      host.addListener(TraceHostPacketHandleEnd, self.handle_no_exceptions)
      host.addListener(TraceHostPacketSend, self.handle_no_exceptions)
    
    for s in patch_panel.switches:
      s.addListener(TraceAsyncSwitchFlowExpiryBegin, self.handle_no_exceptions)
      s.addListener(TraceAsyncSwitchFlowExpiryEnd, self.handle_no_exceptions)
      s.addListener(TraceSwitchPacketHandleBegin, self.handle_no_exceptions)
      s.addListener(TraceSwitchPacketHandleEnd, self.handle_no_exceptions)
      s.addListener(TraceSwitchMessageHandleBegin, self.handle_no_exceptions)
      s.addListener(TraceSwitchMessageHandleEnd, self.handle_no_exceptions)
      s.addListener(TraceSwitchPacketSend, self.handle_no_exceptions)
      s.addListener(TraceSwitchMessageRx, self.handle_no_exceptions)
      s.addListener(TraceSwitchFlowTableRead, self.handle_no_exceptions)
      s.addListener(TraceSwitchFlowTableWrite, self.handle_no_exceptions)
      s.addListener(TraceSwitchFlowTableEntryExpiry, self.handle_no_exceptions)
      s.addListener(TraceSwitchPacketDrop, self.handle_no_exceptions)
      s.addListener(TraceSwitchBufferPut, self.handle_no_exceptions)
      s.addListener(TraceSwitchBufferGet, self.handle_no_exceptions)
      s.addListener(TraceSwitchPacketUpdateBegin, self.handle_no_exceptions)
      s.addListener(TraceSwitchPacketUpdateEnd, self.handle_no_exceptions)
  
  
  def write_event_to_trace(self, event):
    self.write(event.to_json())
  
  #
  # Switch helper functions
  #
  
  def is_async_switch_event_started(self, dpid):
    return dpid in self.started_async_switch_event
  
  def start_async_switch_event(self,dpid,event):
    assert not self.is_async_switch_event_started(dpid)
    self.started_async_switch_event[event.dpid] = event
    assert event.dpid not in self.explicit_successors_async_switch_event
  
  def finish_async_switch_event(self, dpid):
    # sanity check
    assert self.is_async_switch_event_started(dpid)
    # implementation detail check: HbAsyncFlowExpiry should have exactly one TraceSwitchFlowTableEntryExpiry operation
    assert len(self.started_async_switch_event[dpid].operations) == 1
    assert isinstance(self.started_async_switch_event[dpid].operations[0], TraceSwitchFlowTableEntryExpiry)
    self.write_event_to_trace(self.started_async_switch_event[dpid])
    del self.started_async_switch_event[dpid]
    for successor_event in self.explicit_successors_async_switch_event[dpid]:
      self.write_event_to_trace(successor_event)
    del self.explicit_successors_async_switch_event[dpid]
  
  def is_regular_switch_event_started(self, dpid):
    return dpid in self.started_regular_switch_event
    
  def start_regular_switch_event(self,dpid,event):
    # sanity check: cannot start a switch event if one was already started
    #               This would mean that we'd have nested events for 
    #               HbMessageHandle or HbPacketHandle (should not be possible 
    #               to OF 1.0 spec, or a multithreaded switch (our's is not).
    assert not self.is_regular_switch_event_started(dpid)
    # sanity check: should be finished first
    assert not self.is_async_switch_event_started(dpid)
    self.started_regular_switch_event[event.dpid] = event
    assert event.dpid not in self.explicit_successors_regular_switch_event
      
  def finish_regular_switch_event(self, dpid):
    # sanity check
    assert self.is_regular_switch_event_started(dpid)
    # sanity check: should be finished first
    assert not self.is_async_switch_event_started(dpid)
    self.write_event_to_trace(self.started_regular_switch_event[dpid])
    del self.started_regular_switch_event[dpid]
    for successor_event in self.explicit_successors_regular_switch_event[dpid]:
      self.write_event_to_trace(successor_event)
    del self.explicit_successors_regular_switch_event[dpid]
    
  def add_operation_to_switch_event(self, event):
    # sanity check: operations can only be triggered as part of a HbMessageHandle
    #               or HbPacketHandle event.
    assert self.is_async_switch_event_started(event.dpid) or self.is_regular_switch_event_started(event.dpid)
    if self.is_async_switch_event_started(event.dpid):
      # implementation detail check: no HbAsyncFlowExpiry should have more than one removed flow
      assert len(self.started_async_switch_event[event.dpid].operations) == 0
      self.started_async_switch_event[event.dpid].operations.append(event)
    elif self.is_regular_switch_event_started(event.dpid):
      if len(self.started_regular_switch_event[event.dpid].operations) == 1 and type(self.started_regular_switch_event[event.dpid].operations[0]) == TraceSwitchNoOp:
        # remove no-op, as it is no longer needed.
        self.started_regular_switch_event[event.dpid].operations.pop()
      self.started_regular_switch_event[event.dpid].operations.append(event)
      if isinstance(self.started_regular_switch_event[event.dpid], HbMessageHandle):
        # TODO(jm): Factor the following step out into a separate step in hb_graph. We can 
        #           easily add this information later (just scan through the operations).
        # special case for HbMessageHandle
        # Usually HbMessageHandle does not have a packet or in_port field, but if 
        # an output:OFPP_TABLE action is taken then this information should be added
        # (add extra fields for special case HbMessageHandle: through OFPP_TABLE)
        if hasattr(event, 'packet'):
          self.started_regular_switch_event[event.dpid].packet = event.packet
        if hasattr(event, 'in_port'):
          self.started_regular_switch_event[event.dpid].in_port = event.in_port
        
  def try_add_successor_to_switch_event(self, event, mid_in=None, pid_in=None):
    if self.is_async_switch_event_started(event.dpid):
      assert (pid_in == None)
      assert (mid_in is not None)
      self.started_async_switch_event[event.dpid].mid_out.append(mid_in) # link with expiry event
      self.explicit_successors_async_switch_event[event.dpid].append(event)
    elif self.is_regular_switch_event_started(event.dpid):
      assert (mid_in is not None) or (pid_in is not None)
      if mid_in is not None:
        self.started_regular_switch_event[event.dpid].mid_out.append(mid_in) # link with latest event
      if pid_in is not None:
        self.started_regular_switch_event[event.dpid].pid_out.append(pid_in) # link with latest event
      self.explicit_successors_regular_switch_event[event.dpid].append(event)
    else:
      # sanity check
      if ((not hasattr(event, 'msg_type')) or 
              (event.msg_type in (ofp_type_rev_map['OFPT_PACKET_IN'], 
                                  ofp_type_rev_map['OFPT_FLOW_REMOVED'], 
                                  ofp_type_rev_map['OFPT_BARRIER_REPLY']))):
        assert False
      self.write_event_to_trace(event)

  #
  # Host helper functions
  #
    
  def is_host_event_started(self, hid):
    return hid in self.started_host_event

  def start_host_event(self, hid, event):
    # sanity check
    assert not self.is_host_event_started(hid)
    self.started_host_event[hid] = event
    assert event.hid not in self.explicit_successors_host_event
  
  def finish_host_event(self, hid):
    # sanity check
    assert hid in self.started_host_event
    self.write_event_to_trace(self.started_host_event[hid])
    del self.started_host_event[hid]
    for successor_event in self.explicit_successors_host_event[hid]:
      self.write_event_to_trace(successor_event)
    del self.explicit_successors_host_event[hid]
  
  def try_add_successor_to_host_event(self, event, pid_in=None):
    if self.is_host_event_started(event.hid):
      # This event is triggered during the processing of a HostHandle event
      if pid_in is not None:
        # The event that was triggered is capable of having a predecessor, 
        # so let's add the current HostHandle event as the predecessor
        self.started_host_event[event.hid].pid_out.append(pid_in) # add an additional link to latest event
      # Write this event
      self.explicit_successors_host_event[event.hid].append(event)
    else:
      # This event was raised not during the processing of a HostHandle event.
      self.write_event_to_trace(event)
  
  #
  # Switch events
  #
  
  def handle_async_switch_fexp_begin(self, event):
    begin_event = HbAsyncFlowExpiry(dpid=event.dpid)
    self.start_async_switch_event(event.dpid, begin_event)
  
  def handle_async_switch_fexp_end(self, event):
    self.finish_async_switch_event(event.dpid)
  
  def handle_switch_ph_begin(self, event):
    pid_in = self.pids.get_tag(event.packet) # matches a pid_out as the Python object ids will be the same
    
    begin_event = HbPacketHandle(pid_in, dpid=event.dpid, packet=event.packet, in_port=event.in_port)
    self.start_regular_switch_event(event.dpid, begin_event)
  
  def handle_switch_ph_end(self, event):
    self.finish_regular_switch_event(event.dpid)
  
  def handle_switch_mh_begin(self, event):
      mid_in = self.mids.get_tag(event.msg) # filled in, but never matches a mid_out. This link will be filled in by controller instrumentation.
      msg_type = event.msg.header_type
      
      msg_flowmod = None if not hasattr(event, 'flow_mod') else event.flow_mod

      begin_event = HbMessageHandle(mid_in, msg_type, dpid=event.dpid, controller_id=event.controller_id, msg=event.msg, msg_flowmod=msg_flowmod)
      self.start_regular_switch_event(event.dpid, begin_event)
      
      if msg_type == OFPT_BARRIER_REQUEST:
        self.add_operation_to_switch_event(TraceSwitchBarrier(event.dpid))
      else:
        self.add_operation_to_switch_event(TraceSwitchNoOp(event.dpid))
        
      # match with controller instrumentation
      self.unmatched_HbMessageHandle[event.dpid].append((time.time(), mid_in, event.msg))
      self.rematch_unmatched_lines()
  
  def handle_switch_mh_end(self, event):
    self.finish_regular_switch_event(event.dpid)
  
  def handle_switch_ms(self, event):
    mid_in = self.mids.new_tag(event.msg) # tag changes here
    mid_out = self.mids.new_tag(event.msg) # filled in, but never matches a mid_in. This link will be filled in by controller instrumentation. 
    msg_type = event.msg.header_type
    
    # event.msg goes to the controller, and we cannot match it there. So we remove it from the ObjectRegistry.
    self.mids.remove_obj(event.msg)
    
    # it is possible that the message does not have an XID yet. Add one if necessary.
    if event.msg.xid is None:
      event.msg.xid = generateXID()
      
    new_event = HbMessageSend(mid_in, mid_out, msg_type, dpid=event.dpid, controller_id=event.controller_id, msg=event.msg)   
    self.try_add_successor_to_switch_event(new_event, mid_in=mid_in)
    
    # add base64 encoded message to list for controller instrumentation
    # this will always come before the switch has had a chance to write out something, 
    # so no need to check anything here
    self.unmatched_HbMessageSend[event.dpid].append((time.time(), mid_out, event.msg))
    self.rematch_unmatched_lines()
  
  def handle_switch_ps(self, event):
    pid_in = self.pids.new_tag(event.packet) # tag changes here
    pid_out = self.pids.new_tag(event.packet) # tag changes here
    
    new_event = HbPacketSend(pid_in, pid_out, dpid=event.dpid, packet=event.packet, out_port=event.out_port)
    self.try_add_successor_to_switch_event(new_event, pid_in=pid_in)
  
  #
  # Switch operation events
  #

  def handle_switch_table_read(self, event):
    self.add_operation_to_switch_event(event)
    
  def handle_switch_table_write(self, event):
    self.add_operation_to_switch_event(event)
    
  def handle_switch_table_entry_expiry(self, event):
    # TODO(jm): Add case for DELETEs that trigger notifications. For these (reason == delete),
    #           we should add it to the regular switch event, not the async one.
    assert self.is_async_switch_event_started(event.dpid)
    self.add_operation_to_switch_event(event)
    
  def handle_switch_packet_drop(self, event):
    self.add_operation_to_switch_event(event)
    
    
  def handle_switch_buf_put(self, event):
    assert self.is_regular_switch_event_started(event.dpid)
    BufferTypes = (HbPacketHandle, HbMessageHandle) 
    assert isinstance(self.started_regular_switch_event[event.dpid], BufferTypes)
    if isinstance(self.started_regular_switch_event[event.dpid], HbMessageHandle):
      print "Warning: Possible infinite recursion in switch, due to OFPP_TABLE PacketOut."
      # (add extra fields for special case HbMessageHandle: through OFPP_TABLE)
      if hasattr(event, 'packet'):
        self.started_regular_switch_event[event.dpid].packet = event.packet
      if hasattr(event, 'in_port'):
        self.started_regular_switch_event[event.dpid].in_port = event.in_port
        
    # generate pid_out for buffer write
    pid_out = self.pids.new_tag(event.packet) # tag changes here
    self.started_regular_switch_event[event.dpid].pid_out.append(pid_out)
    self.buffer_pids[event.dpid][event.buffer_id] = pid_out
    self.add_operation_to_switch_event(event)
    
  def handle_switch_buf_get(self, event):
    if self.is_regular_switch_event_started(event.dpid):
      assert isinstance(self.started_regular_switch_event[event.dpid], HbMessageHandle)
      # NOTE: do NOT use the current tag of the packet, as it might have already been resent and gotten a much newer pid.
      #       Instead, read the pid_out tag from the buffer put event.
      # For this, we need to check the list of all tags currently stored in buffers.
      if event.buffer_id in self.buffer_pids[event.dpid]:
        self.started_regular_switch_event[event.dpid].pid_in = self.buffer_pids[event.dpid][event.buffer_id]
       
    self.add_operation_to_switch_event(event)
  
  #
  # Switch bookkeeping operations
  #
  
  def handle_switch_rx_wire(self, event):
    """
    Called when a OF message is received over the wire from the switch
    """
    msg = event.msg
    # TODO(jm): use deepcopy instead of base64 here
    b64msg = event.b64msg
    self.msg_to_rxbase64[msg] = b64msg
    
  def handle_switch_tx_wire(self, event):
    """
    Called when a OF message is actually sent over the wire to the switch
    """
    # TODO(jm): do something with this event, e.g. link the original
    #           TraceSwitchMessageSend with this event to make it clear that the
    #           OF message sent in the TraceSwitchMessageSend event was not
    #           dropped by the Fuzzer (see DeferredOFConnection).
    pass
  
  def handle_switch_pu_begin(self, event):
    """
    Mark an object in the ObjectRegistry for an update. This will keep the tags even if the Python object id (memory address) changes.
    """
    tag = self.pids.get_tag(event.packet)
    self.pending_packet_update[event.dpid] = tag
    
  def handle_switch_pu_end(self, event):
    """
    Swap out the marked object in the ObjectRegistry with the new one, while keeping the tags the same.
    """
    assert event.dpid in self.pending_packet_update 
    tag = self.pending_packet_update[event.dpid]
    obj = event.packet
    self.pids.replace_obj(tag, obj)
  
  #
  # Host events
  #
  
  def handle_host_ph_begin(self, event):
    pid_in = self.pids.get_tag(event.packet) # matches a pid_out as the Python object ids will be the same
    
    begin_event = HbHostHandle(pid_in, hid=event.hid, packet=event.packet, in_port=event.in_port)
    self.start_host_event(event.hid, begin_event)
    
  def handle_host_ph_end(self, event):
    self.finish_host_event(event.hid)
    
  def handle_host_ps(self, event):
    pid_in = self.pids.new_tag(event.packet) # tag changes here
    pid_out = self.pids.new_tag(event.packet) # tag changes here
    
    new_event = HbHostSend(pid_in, pid_out, hid=event.hid, packet=event.packet, out_port=event.out_port)
    self.try_add_successor_to_host_event(new_event, pid_in=pid_in)
  
  #
  # Controller instrumentation information
  #
  
  def _get_rxbase64(self, msg):
    """
    Get the message as it was when it was received on the wire, without changes.
    This is actually necessary, as the raw message is often modified as a side
    effect of parsing the message.
    This is especially the case where different Openflow libraries are used
    (e.g. when using a Floodlight controller).
    """
    # TODO(jm): rename method to use deepcopy instead of base64 here
    if msg in self.msg_to_rxbase64:
      return self.msg_to_rxbase64[msg]
    else:
      assert False
    return msg
  
  def _handle_line_match(self, event):
      line = event.line
      match = event.match
      
      self.log.info("Controller instrumentation: "+line)
      
      # Format: match-[data1:data2:....]
      # find end of match
      match_end = line.find(match) + len(match)
      rest_of_line = line[match_end:]
      
      # find start of data
      data_start = rest_of_line.find('[') + 1
      data_end = rest_of_line.find(']')
      
      data_str = rest_of_line[data_start:data_end]
      data = data_str.split(':')
      
      # parse data
      if match == self.controller_hb_msg_in:
        swid = data[0]
        b64msg = data[1]
        self.unmatched_controller_lines.append((time.time(), swid, b64msg))
        
      if match == self.controller_hb_msg_out:
        in_swid = data[0]
        in_b64msg = data[1]
        out_swid = data[2]
        out_b64msg = data[3]
        self.unmatched_controller_lines.append((time.time(), in_swid, in_b64msg, out_swid, out_b64msg))
      self.rematch_unmatched_lines()
    
  # TODO(jm): rename this function to start with _
  def swid_to_dpid(self, swid):
    try:
      return int(swid)
    except ValueError:
      return None
  
  # TODO(jm): rename this function to start with _
  def compare_msg(self, m1, m2):
    def norm (m):
      m = m.clone()
      m.wildcards = m._unwire_wildcards(m.wildcards)
      m.wildcards = m._normalize_wildcards(m.wildcards)
      return m
    if hasattr(m1, 'match') and hasattr(m2, 'match'):
       m1.match = norm(m1.match)
       m2.match = norm(m2.match)
       
    if m1.header_type == OFPT_FLOW_REMOVED and m2.header_type == OFPT_FLOW_REMOVED:
      # TODO(jm): something is seriously wrong with the match fields returned from the controller
      # instrumentation in Floodlight 0.91. For now just compare on all other fields, due to the 
      # duration_nsec field and the xid it is very unlikely that there are collisions.
      return (m1.xid == m2.xid and 
              m1.cookie == m2.cookie and 
              m1.priority == m2.priority and
              m1.reason == m2.reason and
              m1.duration_sec == m2.duration_sec and
              m1.duration_nsec == m2.duration_nsec and
              m1.duration_nsec == m2.duration_nsec and
              m1.idle_timeout == m2.idle_timeout and
              m1.packet_count == m2.packet_count and
              m1.byte_count == m2.byte_count)
    return m1 == m2
  
  # TODO(jm): rename this function to start with _
  def match_controller_line_packet_in(self, dpid, line_msg, unmatched_entry):
    '''
    Returns True if the line was matched to a mid_out
    '''
    timestamp, mid_out, msg = unmatched_entry #tuple
    # TODO(jm): performance: do not decode every time we do the comparison, only decode once
    
    # TODO(jm): hack: we add caching to to this, but it really should be done somewhere else
    if line_msg in self.decoded_line_msg:
      decoded_line_msg = self.decoded_line_msg[line_msg]
    else:
      decoded_line_msg = base64_decode_openflow(line_msg)
      self.decoded_line_msg[line_msg] = decoded_line_msg
    
    if self.compare_msg(msg, decoded_line_msg):
      self.controller_packetin_to_mid_out[(dpid,line_msg)] = mid_out
      temporary_tag = self.mids.generate_unused_tag()
      event = HbControllerHandle(mid_out, temporary_tag)
      first = str(event.eid)
      self.write_event_to_trace(event)
      self.log.info("Adding controller handle ("+first+" -> *): mid_out:"+str(mid_out)+".")
      self.controller_packetin_mid_out_to_HbControllerHandle[mid_out] = event
      self.controller_packetin_mid_out_to_temporary_tag[mid_out] = temporary_tag
      return True
    return False
  
  # TODO(jm): rename this function to start with _
  def match_controller_line_packet_out(self, mid_out, dpid, line_msg, unmatched_entry):
    '''
    Returns True if the line was matched to a mid_in
    '''
    timestamp, mid_in, msg = unmatched_entry #tuple
    # TODO(jm): performance: do not decode every time we do the comparison, only decode once
    # TODO(jm): performance: do not fetch rxbase64 every time, only do it once
    
    # TODO(jm): hack: we add caching to to this, but it really should be done somewhere else
    if msg in self.decoded_msg_to_rxbase64:
      decoded_msg = self.decoded_msg_to_rxbase64[msg]
    else:
      decoded_msg = base64_decode_openflow(self._get_rxbase64(msg))
      self.decoded_msg_to_rxbase64[msg] = decoded_msg
    if line_msg in self.decoded_line_msg:
      decoded_line_msg = self.decoded_line_msg[line_msg]
    else:
      decoded_line_msg = base64_decode_openflow(line_msg)
      self.decoded_line_msg[line_msg] = decoded_line_msg
    
    if self.compare_msg(decoded_msg, decoded_line_msg):
      first_event = self.controller_packetin_mid_out_to_HbControllerHandle[mid_out]
      temporary_tag = self.controller_packetin_mid_out_to_temporary_tag[mid_out]
      second_event = HbControllerSend(temporary_tag, mid_in)
      first = str(first_event.eid)
      second = str(second_event.eid)
      self.write_event_to_trace(second_event)
      self.log.info("Adding controller send with edge ("+first+" -> "+second+"): mid_out:"+str(mid_out)+" -> mid_in:"+str(mid_in)+".")
      return True
    return False
  
  # TODO(jm): rename this function to start with _
  def match_controller_line(self, line):
    '''
    Returns True if the line was matched
    '''
    # TODO(jm): Process all lines with length 3 first, then all longer lines.
    if len(line) == 3:
      timestamp, in_swid, in_msg = line
      # PACKET_IN <==> find mid_out, add link to self.controller_packetin_to_mid_out
      in_dpid = self.swid_to_dpid(in_swid)
      if in_dpid is None:
        # the controller did not supply the dpid, no way for us to ever match it
        print 'Error: Discarding controller line: ' + str(line)
        return True
      else:
        # we know this switch
        for unmatched_entry in self.unmatched_HbMessageSend[in_dpid]:
          if self.match_controller_line_packet_in(in_dpid, in_msg, unmatched_entry):
            # we know this message
#             print "====> MATCHED: age: {} - {}: {}".format(str(time.time()-unmatched_entry[0]), in_dpid, str(unmatched_entry[2]))
            self.unmatched_HbMessageSend[in_dpid].remove(unmatched_entry) # okay as we exit the loop now
            return True
      return False
    elif len(line) == 5:
      timestamp, in_swid, in_msg, out_swid, out_msg = line
      # PACKET_IN
      in_dpid = self.swid_to_dpid(in_swid)
      if in_dpid is None:
        # the controller did not supply the dpid, no way for us to ever match it
        print 'Error: Discarding controller line: ' + line
        assert False
        return True
      else:
        # we know the in switch
        if (in_dpid,in_msg) in self.controller_packetin_to_mid_out:
          mid_out = self.controller_packetin_to_mid_out[(in_dpid,in_msg)]
          # we know the in event
          # PACKET_OUT/FLOW_MOD <==> find mid_in, add HB edge
          out_dpid = self.swid_to_dpid(out_swid)
          if out_dpid is None:
            # the controller did not supply the dpid, no way for us to ever match it
            print 'Error: Discarding controller line: ' + line
            assert False
            return True
          else:
            # we know the out switch
            for unmatched_entry in self.unmatched_HbMessageHandle[out_dpid]:
              if self.match_controller_line_packet_out(mid_out, out_dpid, out_msg, unmatched_entry):
                # we know this message, and an edge was added
#                 print "====> MATCHED: age: {} - {}: {}".format(str(time.time()-unmatched_entry[0]), out_dpid, str(unmatched_entry[2]))
                self.unmatched_HbMessageHandle[out_dpid].remove(unmatched_entry) # okay as we exit the loop now
                return True
      return False

  # TODO(jm): rename this function to start with _
  def rematch_unmatched_lines(self):
    # self.unmatched_controller_lines[:] modifies the list slice instead of assigning a new list
    self.unmatched_controller_lines = list(itertools.ifilterfalse(self.match_controller_line, self.unmatched_controller_lines))
    print "Controller log: {} log lines, {} STS events not matched.".format(len(self.unmatched_controller_lines), len(self.unmatched_HbMessageHandle) + len(self.unmatched_HbMessageSend))


  # TODO(jm): Remove this function
  def diff_flow_mods(self, b1, b2):
    """
    For debugging. Print out both flow mods given in base64.
    """
    import base64
    def decode_flow_mod(data):
      if data is None:
        return None
      bits = base64.b64decode(data)
      fm = ofp_flow_mod()
      fm.unpack(bits) # NOTE: unpack IS in-situ for ofp_flow_mod() type
      return fm
    
    fm1 = decode_flow_mod(b1)
    fm2 = decode_flow_mod(b2)
    print str(fm1)
    print str(fm2)