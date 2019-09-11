import pygame
import socket
import threading
import TermHelper
import Queue
#import struct

#uint32_t = struct.Struct("<I")

class PygReplInst(object):
    def __init__(self):
        self.CmdQueue = Queue.Queue()
        self.RetVal = ("", 0)
        self.ExecLock = threading.Lock()
    def ThrdReplRunner(self, In, globs, locs):
        with self.ExecLock:
            self.CmdQueue.put((In, globs, locs))
            pygame.event.post(pygame.event.Event(pygame.USEREVENT, {"ReplInst": self}))
            self.CmdQueue.join()
            return self.RetVal
    def MainFn(self):
        In, globs, locs = self.CmdQueue.get()
        self.RetVal = TermHelper.DefReplRunner(In, globs, locs)
        self.CmdQueue.task_done()

STAT_PRESTART = 4
STAT_STARTING = 3
STAT_RUNNING = 2
STAT_EXITING = 1
STAT_STOPPED = 0
class MainApp(object):
    def __init__(self, ReplInst):
        self.Listeners = []
        self.Connections = []
        self.Status = STAT_PRESTART
        self.ListenTimeout = 0.25
        self.ReplInst = ReplInst
        self.ConnLock = threading.Lock()
        self.HostLock = threading.Lock()
    def OpenListenSocket(self, af, typ, proto, addr):
        try:
            sock = socket.socket(af, typ, proto)
            sock.bind(addr)
            sock.settimeout(self.ListenTimeout)
            return sock
        except socket.error:
            return None
    def PreStart(self, host, port):
        AddrData = socket.getaddrinfo(host, port)
        LstSocks = [None] * len(AddrData)
        for c, (af, typ, proto, ca, addr) in enumerate(AddrData):
            sock = self.OpenListenSocket(af, typ, proto, addr)
            if sock is None: continue
            LstSocks[c] = (sock, addr)
        LstSocks = filter(None, LstSocks)
        self.Status = STAT_STARTING
        return LstSocks
    def Start(self, LstSocks):
        ThrdsToStart = [None] * len(LstSocks)
        with self.HostLock:
            assert len(self.Listeners) == 0
            for c, (sock, addr) in enumerate(LstSocks):
                args = [self, sock, addr, None]
                Thrd = threading.Thread(
                    target=MainApp.ListenerThread, args=args, name="Listener: %s" % repr(addr))
                args[-1] = Thrd
                ThrdsToStart[c] = Thrd
            self.Listeners = list(ThrdsToStart)
        for Thrd in ThrdsToStart:
            Thrd.start()
        self.Status = STAT_RUNNING
    def Exit(self):
        self.Status = STAT_EXITING
    def ShouldStop(self):
        return self.Status < STAT_RUNNING
    def ConnectionThread(self, sock, addr, Thrd):
        TermObj = TermHelper.BareSockTerm(sock)
        locs = {}
        TermHelper.ReplShell1(TermObj, globals(), locs, ">>> ", "... ", self.ReplInst.ThrdReplRunner, self.ShouldStop)
        TermObj.ExitTerm()
        with self.ConnLock:
            self.Connections.remove(Thrd)
    def CheckExit(self):
        with self.ConnLock:
            if len(self.Connections):
                return False
        with self.HostLock:
            if len(self.Listeners):
                return False
        self.Status = STAT_STOPPED
        return True
    def ListenerThread(self, sock, addr, ThisThrd):
        sock.listen(1)
        while self.Status >= STAT_RUNNING:
            res = None
            try:
                res = sock.accept()
            except socket.timeout:
                pass
            if res is None:
                continue
            conn, addr = res
            args = [self, conn, addr, None]
            Thrd = threading.Thread(
                target=MainApp.ConnectionThread, name="Conn: %s" % repr(addr), args=args)
            args[3] = Thrd
            with self.ConnLock:
                self.Connections.append(Thrd)
            Thrd.start()
        with self.HostLock:
            self.Listeners.remove(ThisThrd)
Surf = None
def Main():
    global Surf
    ReplInst = PygReplInst()
    AppInst = MainApp(ReplInst)
    LstSocks = AppInst.PreStart(socket.gethostname(), 2500)
    print "Listening on %s" % ", ".join(map(lambda (sock, addr): repr(sock.getsockname()), LstSocks))
    AppInst.Start(LstSocks)
    pygame.init()
    Surf = pygame.display.set_mode((640, 480))
    while True:
        Evt = pygame.event.wait()
        if Evt.type == pygame.QUIT:
            AppInst.Exit()
            break
        elif Evt.type == pygame.USEREVENT:
            Evt.ReplInst.MainFn()
    while not AppInst.CheckExit():
        Evt = pygame.event.wait()
        if Evt.type == pygame.USEREVENT:
            Evt.ReplInst.MainFn()
    pygame.quit()

Main()
