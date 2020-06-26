from __future__ import division, unicode_literals, print_function, absolute_import
from threading import Thread, Event
from zprocess import ZMQServer, Process
try:
    from zprocess.process_tree import ReadQueue, WriteQueue
except ImportError:
    from zprocess import ReadQueue, WriteQueue
import zmq
import os


def to_local(path, prefix_remote):
    global prefix_local
    if path.startswith(prefix_remote):
        path = path.split(prefix_remote, 1)[1]
        path = prefix_local + path
        path = path.replace(os.path.sep, '\\')
    return path


def forward(forward_from, forward_to, stop_event, shared_drive=""):
    # Forward messages untill Killed
    while not stop_event.wait(0):
        try:
            success, message, results = forward_from.get(timeout=1)
            if shared_drive != "" and type(message) is tuple and len(message) > 2:
                message = list(message)
                message[1] = to_local(message[1], shared_drive)
                message = tuple(message)
            # for i, mess in enumerate(message):
            #   print(i, mess)
            forward_to.put((success, message, results))
            # if not success and message == 'quit':
            #     break
        except Exception as e:
            pass


class WorkerServer(ZMQServer):
    def __init__(self, port, prefix_local='Z:\\', **kwargs):
        ZMQServer.__init__(self, port, **kwargs)
        self.workers = {}
        self.kill_threads = {}
        self.prefix_local = prefix_local

    def handler(self, message):
        action = message['action']
        name = message['name']
        device_name = message['device_name']

        if action == 'start':
            workerargs = message['workerargs']
            port_from_worker = message['port_from_worker']
            address_from_worker = message['address_from_worker']
            shared_drive_remote = message['shared_drive']

            # initialize dict for workers and Thread-kill-commands
            if device_name not in self.workers:
                self.workers[device_name] = {}
                self.kill_threads[device_name] = {}

            # Terminate old Worker before creating an new one
            if name in self.workers[device_name]:
                self.terminate_worker(device_name, name)

            # create Worker and Thread-kill-command
            print("Initializing (Device: {}, Worker: {})".format(device_name, name))
            WorkerClass = message['WorkerClass']
            if isinstance(WorkerClass, type):
                self.workers[device_name][name] = WorkerClass()
            elif isinstance(WorkerClass, str):
                # If we were passed a string for the WorkerClass, it is an import path
                # for where the Worker class can be found. Pass it to zprocess.Process,
                # which will do the import in the subprocess only.
                self.workers[device_name][name] = Process(
                    output_redirection_port=self._output_box.port,
                    subclass_fullname=WorkerClass,
                )
            else:
                raise TypeError(WorkerClass)
            to_worker, from_worker = self.workers[device_name][name].start(name, device_name, workerargs)
            self.kill_threads[device_name][name] = Event()

            # return forwarded ports
            return self.initialize_forwarding(device_name, name, to_worker, from_worker, port_from_worker, address_from_worker, shared_drive_remote)

        elif action == 'terminate':
            return self.terminate_worker(device_name, name)

    def initialize_forwarding(self, device_name, name, to_worker, from_worker, port, address, shared_drive_remote):
        context = zmq.Context(1)
        from_extern_sock = context.socket(zmq.PULL)
        port_from_extern = from_extern_sock.bind_to_random_port('tcp://*')
        from_extern = ReadQueue(from_extern_sock, None)

        to_extern_sock = context.socket(zmq.PUSH)
        to_extern_sock.connect('tcp://{}:{}'.format(address, port))
        to_extern = WriteQueue(to_extern_sock)

        thread_to_worker = Thread(target=forward, args=(from_extern, to_worker, self.kill_threads[device_name][name], shared_drive_remote))
        thread_to_worker.daemon = True
        thread_to_worker.start()

        thread_from_worker = Thread(target=forward, args=(from_worker, to_extern, self.kill_threads[device_name][name]))
        thread_from_worker.daemon = True
        thread_from_worker.start()

        return port_from_extern

    def terminate_worker(self, device_name, name):
        print("Terminating (Device: {}, Worker: {})".format(device_name, name))
        # trigger Thread Kill Command
        if device_name in self.kill_threads and name in self.kill_threads[device_name]:
            self.kill_threads[device_name][name].set()

        # terminate Worker
        if device_name in self.workers and name in self.workers[device_name]:
            worker = self.workers[device_name].pop(name)
            worker.terminate()
        return True

    def shutdown(self, signal, frame):
        # Terminate all aktive workers
        for device_name in self.workers.keys():
            for name in self.workers[device_name].keys():
                self.terminate_worker(device_name, name)

        print("\nExiting")
        sys.exit(0)


if __name__ == '__main__':
    # Start experiment server
    import socket
    import sys
    import signal
    import time
    from labscript_utils.labconfig import LabConfig

    # config
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    else:
        port = 5789

    _config = LabConfig(required_params={'paths': ['shared_drive']})
    prefix_local = _config.get('paths', 'shared_drive')
    pub_sub_active = False
    if pub_sub_active:
        sub_port = _config.get('ports', 'blacs_broker_sub')
        pub_port = 50354
        sub_server = '192.168.1.115'

    # Start Worker Server
    print("Starting Worker Server on IP {} Port {} to exit press CTRL + C".format(socket.gethostbyname(socket.gethostname()), port))
    worker_server = WorkerServer(port, prefix_local=prefix_local)

    # On Shutdown close all aktive workers
    signal.signal(signal.SIGINT, worker_server.shutdown)

    if pub_sub_active:
        context = zmq.Context(1)

        # Socket facing clients
        frontend = context.socket(zmq.SUB)
        frontend.bind("tcp://*:{}".format(sub_port))
        frontend.setsockopt(zmq.SUBSCRIBE, "".encode('utf-8'))

        # Socket facing services
        backend = context.socket(zmq.PUB)
        backend.connect("tcp://{}:{}".format(sub_server, pub_port))
        zmq.device(zmq.FORWARDER, frontend, backend)
    else:
        while True:
            # reduce CPU usage by long sleep periods
            time.sleep(10)
