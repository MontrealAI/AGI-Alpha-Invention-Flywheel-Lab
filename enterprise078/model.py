FAMILIES = {
 'reliable_readback': (True, False, False, False),
 'persistent_idempotency': (False, True, False, False),
 'both_capabilities': (True, True, False, False),
 'unobservable_nonidempotent': (False, False, False, False),
 'stale_readback': (True, False, True, False),
 'expiring_dedup': (False, True, False, True),
}
FAULTS = ('ack', 'drop_before', 'drop_after')

class Instrument:
 def __init__(self, family):
  self.readable,self.dedup,self.stale,self.expiring=FAMILIES[family]
  self.effects={};self.seen=set();self.trace=[]
 def command(self,key,quantity,fault='ack'):
  if self.expiring: self.seen.clear()
  if fault!='drop_before' and (not self.dedup or key not in self.seen):
   self.effects[key]=self.effects.get(key,0)+quantity;self.seen.add(key)
  response='unknown' if fault!='ack' else 'ok'
  self.trace.append({'action':'command','key':key,'quantity':quantity,'fault':fault,'response':response})
  return response
 def query(self,key):
  response='unsupported' if not self.readable else bool(key in self.effects and not self.stale)
  self.trace.append({'action':'query','key':key,'response':response})
  return response

def execute(device,policy,key,quantity,fault):
 start=len(device.trace)
 response=device.command(key,quantity,fault)
 if response=='unknown':
  if policy=='retry_same_key': device.command(key,quantity)
  elif policy=='read_before_retry':
   response=device.query(key)
   if response is False: device.command(key,quantity)
   elif response!='unsupported': pass
   else: return False,device.trace[start:]
  else: return False,device.trace[start:]
 return True,device.trace[start:]
