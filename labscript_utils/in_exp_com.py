from queue import SimpleQueue 

class InExperimentCom(object):
    def __init__(self, device_ids):
        self.broadcast_queues = {}
        self.to_master_queue = SimpleQueue()
        for id in device_ids:
            self.broadcast_queues[id] = SimpleQueue()
            
    def broadcast(self, msg):
        for key in self.broadcast_queues:
            self.broadcast_queues[key].put(msg)
            
    def device_get(self, device_id):
        return self.broadcast_queues[device_id].get()
            
    def master_get(self):
        return self.to_master_queue.get()
    
    def to_master(self, device_id, msg):
        self.to_master_queue.put({"id": device_id, "msg": msg})