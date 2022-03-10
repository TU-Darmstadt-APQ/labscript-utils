import zmq
import queue
import time
import threading


STATE_INITIALIZING = 'INIT'

STATE_BUFFERED = 'BUFFERED'
STATE_MANUAL = 'MANUAL'

STATE_READY = 'READY'
STATE_RUNNING = 'RUNNING'
STATE_FINISHED = 'FINISHED'


INIT_TIMEOUT = 1

SLEEP_TIME_MANUAL = 1e-3
SLEEP_TIME_EXPERIMENT = 1


class RunMasterClass(object):

    def __init__(self, to_master_port='43227', from_master_port='43228'):

        self.command_queue = queue.SimpleQueue()
        self.state = STATE_MANUAL

        def dummy_next_section_callback():
            return -1
        self.compute_next_section_callback = dummy_next_section_callback

        self.context = zmq.Context()

        self.to_master_com = self.context.socket(zmq.PULL)
        self.from_master_com = self.context.socket(zmq.PUB)

        self.to_master_com.set_hwm(0)
        self.from_master_com.set_hwm(0)

        self.to_master_com.bind(f"tcp://*:{to_master_port}")
        self.from_master_com.bind(f"tcp://*:{from_master_port}")

        self.device_state = {}
        self.run_thread = None

        self.test_counter = 0

    def set_compute_next_section_callback(self, callback):
        self.compute_next_section_callback = callback

    def send_buffered(self):
        self.command_queue.put("to_buffered")

    def send_start(self):
        self.command_queue.put("start")

    def abort(self):
        self.command_queue.put("abort")

    def shutdown(self):
        self.command_queue.put("shutdown")
        if self.run_thread is not None:
            self.run_thread.join()

        self.to_master_com.close()
        self.from_master_com.close()
        self.context.term()

    def start(self):
        self.run_thread = threading.Thread(target=self.mainloop)
        self.run_thread.start()

    def mainloop(self):

        time.sleep(1)
        print("start mainloop")
        self.from_master_com.send(b"greet")
        print("sent greet me")

        while True:

            # check & process new messages
            if self.state == STATE_MANUAL or self.state == STATE_INITIALIZING:
                timeout = SLEEP_TIME_MANUAL
            else:
                timeout = SLEEP_TIME_EXPERIMENT

            events = self.to_master_com.poll(timeout=timeout, flags=zmq.POLLIN)
            while events != 0:
                msg = self.to_master_com.recv()
                events -= 1

                print(f"recv: {msg}")

                if msg == b"abort":
                    self.command_queue.put("abort")

                elif msg.startswith(b"hello"):
                    if self.state != STATE_MANUAL:
                        raise Exception(b"Can only add devices when in manual mode")
                    device = msg.split(b' ')[1]
                    print(f"Register {device}")
                    self.device_state[device] = STATE_MANUAL

                elif msg.startswith(b"fin"):
                    if self.state != STATE_RUNNING:
                        raise Exception("Can only finish devices when in running state")
                    device = msg.split(b' ')[1]
                    self.device_state[device] = STATE_FINISHED

                elif msg.startswith(b"rdy"):
                    if self.state != STATE_FINISHED:
                        raise Exception("Can only get ready devices when in finished state")
                    device = msg.split(b' ')[1]
                    self.device_state[device] = STATE_READY

            # Process command queue
            while not self.command_queue.empty():
                try:
                    # Queue still may be empty by pythons definition
                    msg = self.command_queue.get(False, 0)
                except queue.Empty:
                    # Finish loop as queue is empty
                    break

                if msg == "shutdown":
                    print("Shutting down")
                    self.from_master_com.send(b"shutdown")
                    return

                elif msg == "to_buffered":
                    print("To buffered")
                    self.test_counter = 0
                    if self.state == STATE_MANUAL:
                        self.state = STATE_BUFFERED
                        for dev in self.device_state:
                            self.device_state[dev] = STATE_READY

                elif msg == "start":
                    if self.state!= STATE_BUFFERED:
                        raise Exception("Must be buffered to start!")
                    print("Start")
                    self.from_master_com.send(b"start")
                    self.state = STATE_RUNNING
                    for dev in self.device_state:
                        self.device_state[dev] = STATE_RUNNING

                elif msg == "abort":
                    self.from_master_com.send(b"abort")
                    self.state = STATE_MANUAL

            # Do state transitions
            if self.state == STATE_RUNNING:
                # Check whether devices are finished
                all_finished = True
                for dev in self.device_state:
                    if self.device_state[dev] != STATE_FINISHED:
                        all_finished = False
                        break

                if all_finished:
                    # Compute next section or exit
                    next_section = self.compute_next_section_callback()

                    if next_section == -1:
                        self.from_master_com.send(b"exit")
                        self.state = STATE_MANUAL
                    else:
                        self.from_master_com.send(str.encode(f"load {next_section}"))
                        self.state = STATE_FINISHED

            elif self.state == STATE_FINISHED:
                # Check whether devices are ready again
                all_finished = True
                for dev in self.device_state:
                    if self.device_state[dev] != STATE_READY:
                        all_finished = False
                        break
                if all_finished:
                    self.from_master_com.send(b"start")
                    for dev in self.device_state:
                        self.device_state[dev] = STATE_RUNNING
                    self.state = STATE_RUNNING


class RunBaseClass(object):

    def __init__(self, name, master_ip, to_master_port='43227', from_master_port='43228'):
        self.state = STATE_MANUAL
        self.command_queue = queue.SimpleQueue()
        self.name = name

        def dummy_callback_1():
            return True

        def dummy_callback_2(arg):
            return True

        self.is_finished_callback = dummy_callback_1
        self.start_callback = dummy_callback_1
        self.load_next_section_callback = dummy_callback_2

        self.context = zmq.Context()

        self.to_master_com = self.context.socket(zmq.PUSH)
        self.from_master_com = self.context.socket(zmq.SUB)

        self.to_master_com.set_hwm(0)
        self.from_master_com.set_hwm(0)

        self.from_master_com.setsockopt(zmq.SUBSCRIBE, b"")

        self.to_master_com.connect(f"tcp://{master_ip}:{to_master_port}")
        self.from_master_com.connect(f"tcp://{master_ip}:{from_master_port}")

        self.run_thread = None

    def set_is_finished_callback(self, callback):
        self.is_finished_callback = callback
        
    def set_start_callback(self, callback):
        self.start_callback = callback

    def set_load_next_section_callback(self, callback):
        self.load_next_section_callback = callback

    def send_buffered(self):
        self.command_queue.put("to_buffered")

    def abort(self):
        self.command_queue.put("abort")

    def shutdown(self):
        self.command_queue.put("shutdown")
        if self.run_thread is not None:
            self.run_thread.join()

        self.to_master_com.close()
        self.from_master_com.close()
        self.context.term()

    def start(self):
        self.run_thread = threading.Thread(target=self.mainloop)
        self.run_thread.start()

    def mainloop(self):

        self.to_master_com.send(str.encode(f"hello {self.name}"))
        self.state = STATE_MANUAL
        print("Enter mainloop")

        while True:

            # check & process new messages
            if self.state == STATE_MANUAL or self.state == STATE_INITIALIZING:
                timeout = SLEEP_TIME_MANUAL
            else:
                timeout = SLEEP_TIME_EXPERIMENT

            events = self.from_master_com.poll(timeout=timeout, flags=zmq.POLLIN)
            while events != 0:
                msg = self.from_master_com.recv()
                events -= 1

                print(f"recv {self.name}: {msg}")

                if msg == b"abort":
                    self.command_queue.put("abort")

                elif msg == b"shutdown":
                    self.command_queue.put("shutdown")

                elif msg == b"start":
                    if self.state != STATE_READY:
                        raise Exception("Device not ready for start.")
                    self.state = STATE_RUNNING
                    self.start_callback()

                elif msg.startswith(b"load"):
                    if self.state != STATE_FINISHED:
                        raise Exception("Device not finished yet.")
                    next_section = int(msg.split(b' ')[1])
                    print(f"load next section {next_section}")
                    self.load_next_section_callback(next_section)
                    self.to_master_com.send(str.encode(f"rdy {self.name}"))
                    self.state = STATE_READY

                elif msg == b"exit":
                    if self.state != STATE_FINISHED:
                        raise Exception("Device not finished yet.")
                    self.state = STATE_MANUAL

                elif msg == b"greet":
                    if self.state != STATE_MANUAL:
                        raise Exception("Can only greed in manual state.")
                    self.to_master_com.send(str.encode(f"hello {self.name}"))


            while not self.command_queue.empty():
                try:
                    # Queue still may be empty by pythons definition
                    msg = self.command_queue.get(False, 0)
                except queue.Empty:
                    # Finish loop as queue is empty
                    break

                if msg == "shutdown":
                    print("Shutting down")
                    return
                elif msg == "abort":
                    self.state = STATE_MANUAL
                elif msg == "to_buffered":
                    if not self.state == STATE_MANUAL:
                        raise Exception("Must be in manual mode to transition to buffered")
                    self.state = STATE_READY

            # State stuff
            if self.state == STATE_RUNNING:
                if self.is_finished_callback():
                    self.to_master_com.send(str.encode(f"fin {self.name}"))
                    self.state = STATE_FINISHED

