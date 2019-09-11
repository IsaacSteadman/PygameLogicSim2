import pygame
import TermHelper
import threading
import socket
import Queue
import PygCtl


class PygReplInst(object):
    def __init__(self, evt_id=pygame.USEREVENT):
        self.evt_id = evt_id
        self.cmd_queue = Queue.Queue()
        self.ret_val = ("", 0)
        self.exec_lk = threading.Lock()

    def thrd_repl_runner(self, inp, globs, locs):
        with self.exec_lk:
            self.cmd_queue.put((inp, globs, locs))
            pygame.event.post(pygame.event.Event(self.evt_id, {"repl_inst": self}))
            self.cmd_queue.join()
            return self.ret_val

    def main_fn(self):
        inp, globs, locs = self.cmd_queue.get()
        self.ret_val = TermHelper.DefReplRunner(inp, globs, locs)
        self.cmd_queue.task_done()


STAT_PRESTART = 4
STAT_STARTING = 3
STAT_RUNNING = 2
STAT_EXITING = 1
STAT_STOPPED = 0

# OR means OverRide
OR_NONE = 0
OR_OVERWRITE = 1
OR_INSERT_BETWEEN = 2


class ReplApp(object):
    def __init__(self, repl_inst):
        """
        :param PygReplInst repl_inst:
        """
        self.listeners = []
        self.connections = []
        self.status = STAT_PRESTART
        self.listen_timeout = 0.25
        self.repl_inst = repl_inst
        self.conn_lock = threading.Lock()
        self.host_lock = threading.Lock()

    def open_listen_socket(self, af, typ, proto, addr):
        try:
            sock = socket.socket(af, typ, proto)
            sock.bind(addr)
            sock.settimeout(self.listen_timeout)
            return sock
        except socket.error:
            return None

    def attach_to_pyg_ctl(self, override=OR_NONE):
        if override == OR_NONE:
            assert self.repl_inst.evt_id not in PygCtl.DctEvtFunc, "cannot attach (use OR_OVERWRITE or OR_INSERT_BETWEEN)"

            def on_evt_fn(evt):
                evt.repl_inst.main_fn()
        elif override == OR_OVERWRITE:
            def on_evt_fn(evt):
                evt.repl_inst.main_fn()
        elif override == OR_INSERT_BETWEEN:
            fn = PygCtl.DctEvtFunc.get(self.repl_inst.evt_id, None)
            if fn is None:
                def on_evt_fn(evt):
                    evt.repl_inst.main_fn()
            else:
                def on_evt_fn(evt):
                    fn(evt)
                    evt.repl_inst.main_fn()
        else:
            raise ValueError("Expected override to be one of OR_NONE, OR_OVERWRITE, OR_INSERT_BETWEEN")
        PygCtl.DctEvtFunc[self.repl_inst.evt_id] = on_evt_fn

    def pre_start(self, host, port):
        addr_data = socket.getaddrinfo(host, port)
        lst_socks = [None] * len(addr_data)
        for c, (af, typ, proto, ca, addr) in enumerate(addr_data):
            sock = self.open_listen_socket(af, typ, proto, addr)
            if sock is None: continue
            lst_socks[c] = (sock, addr)
        lst_socks = filter(None, lst_socks)
        self.status = STAT_STARTING
        return lst_socks

    def start(self, lst_socks, globs_or=None, locs_or=None):
        thrds_to_start = [None] * len(lst_socks)
        with self.host_lock:
            assert len(self.listeners) == 0
            for c, (sock, addr) in enumerate(lst_socks):
                args = [self, sock, addr, None, globs_or, locs_or]
                thrd = threading.Thread(
                    target=ReplApp.listener_thread, args=args, name="Listener: %s" % repr(addr))
                args[3] = thrd
                thrds_to_start[c] = thrd
            self.listeners = list(thrds_to_start)
        for thrd in thrds_to_start:
            thrd.start()
        self.status = STAT_RUNNING

    def exit(self):
        self.status = STAT_EXITING

    def should_stop(self):
        return self.status < STAT_RUNNING

    def connection_thread(self, sock, addr, thrd, globs_or=None, locs_or=None):
        if sock is not None:
            term_obj = TermHelper.BareSockTerm(sock)
            globs = globals() if globs_or is None else (globs_or() if callable(globs_or) else globs_or)
            locs = {} if locs_or is None else (locs_or() if callable(locs_or) else locs_or)
            assert isinstance(locs, dict), "got " + repr(locs)
            assert isinstance(globs, dict), "got " + repr(globs)
            TermHelper.ReplShell1(term_obj, globs, locs, ">>> ", "... ", self.repl_inst.thrd_repl_runner, self.should_stop)
            term_obj.ExitTerm()
        else:
            print "expected socket to not be None"
        with self.conn_lock:
            self.connections.remove(thrd)

    def check_exit(self):
        with self.conn_lock:
            if len(self.connections):
                return False
        with self.host_lock:
            if len(self.listeners):
                return False
        self.status = STAT_STOPPED
        return True

    def listener_thread(self, sock, addr, this_thrd, globs_or=None, locs_or=None):
        sock.listen(1)
        while self.status >= STAT_RUNNING:
            res = None
            try:
                res = sock.accept()
            except socket.timeout:
                pass
            if res is None:
                continue
            conn, addr = res
            print "Accepted connection", addr
            args = [self, conn, addr, None, globs_or, locs_or]
            thrd = threading.Thread(
                target=ReplApp.connection_thread, name="Conn: %s" % repr(addr), args=args)
            args[3] = thrd
            with self.conn_lock:
                self.connections.append(thrd)
            thrd.start()
        with self.host_lock:
            self.listeners.remove(this_thrd)
