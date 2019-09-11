import traceback
import threading
import sys
import socket
import select
try:
    import readline
except ImportError:
    try:
        import pyreadline as readline
    except ImportError:
        readline = None
        raise ImportError("Could not import pyreadline")
try:
    xrange
except NameError:
    xrange = range


def GetLongStrBytes(byts):
    """
    :type byts: str
    :rtype: int|long
    """
    p = 1
    rtn = 0
    for byt in byts:
        rtn += p * ord(byt)
        p *= 256
    return rtn


def AlignStrBytesLong(l, align):
    rtn = ""
    while l > 0:
        rtn += chr(l % 256)
        l /= 256
    return rtn + "\0" * (align - len(rtn))


def PackStrLen(s, headlen):
    return AlignStrBytesLong(len(s), headlen) + s

class BaseTerm(object):
    def PrintLk(self, *args):
        raise NotImplementedError("Not Implemented")

    def Print(self, *args):
        raise NotImplementedError("Not Implemented")
    
    def Write(self, s):
        raise NotImplementedError("Not Implemented")
    
    def WriteLk(self, s):
        raise NotImplementedError("Not Implemented")
    
    def WriteErr(self, s):
        self.Write(s)
    
    def WriteErrLk(self, s):
        self.WriteLk(s)
    
    def ReadLine(self, prompt=""):
        return ""
    
    def ReadPass(self, prompt=""):
        return self.ReadLine(prompt)

    def ExitTerm(self):
        raise NotImplementedError("Not Implemented")


class CmdTerm(BaseTerm):
    def __init__(self):
        self.Prompt = None
        self.Lk = threading.Lock()
    
    def ReadLine(self, prompt=""):
        self.Prompt = prompt
        Rtn = input(self.Prompt)
        self.Prompt = None
        return Rtn
    
    def Write(self, s):
        self.PreWrite(s)
        sys.stdout.write(s)
        self.PostWrite(s)
    
    def WriteLk(self, s):
        with self.Lk:
            self.Write(s)
    
    def WriteErr(self, s):
        self.PreWrite(s)
        sys.stderr.write(s)
        self.PostWrite(s)
    
    def WriteErrLk(self, s):
        with self.Lk:
            self.WriteErr(s)
    
    def Print(self, *args):
        self.Write(" ".join(map(str, args))+"\n")
    
    def PrintLk(self, *args):
        with self.Lk:
            self.Print(*args)
    
    def PreWrite(self, str_log):
        if self.Prompt is not None:
            lenLine = len(readline.get_line_buffer())+len(self.Prompt)
            sys.stdout.write("\r"+" "*lenLine+"\r")
    
    def PostWrite(self, str_log):
        if self.Prompt is not None:
            sys.stdout.write(self.Prompt + readline.get_line_buffer())
            sys.stdout.flush()
    
    def LoggerPreW(self, log, c, str_log):
        if log.LstFl[c] == sys.stdout:
            self.PreWrite(str_log)
    
    def LoggerPostW(self, log, c, str_log):
        if log.LstFl[c] == sys.stdout:
            self.PostWrite(str_log)


#messages always follow the same format
#when a message is sent a response is expected in order for the action to finish
def MsgSockThrd(SockProt, Step=1, TmOutHandler=None):
    while SockProt.IsOpen:
        CurTmOut = SockProt.Sock.gettimeout()
        while SockProt.IsOpen:
            Rtn = None
            if CurTmOut is None or Step < CurTmOut:
                Rtn = select.select([SockProt.Sock], [], [], Step)[0]
                if CurTmOut is not None: CurTmOut -= Step
            else:
                Rtn = select.select([SockProt.Sock], [], [], CurTmOut)[0]
                CurTmOut = 0
            if len(Rtn) > 0: break
            elif CurTmOut is None: pass
            elif CurTmOut == 0:
                if TmOutHandler is None or not TmOutHandler(SockProt):
                    with SockProt.SockLk:
                        SockProt.IsOpen = False
                        SockProt.SockCond.notify_all()
                    break
                else: CurTmOut = SockProt.Sock.gettimeout()
        if not SockProt.IsOpen: break
        Str = SockProt.Sock.recv(1)
        if len(Str) == 0:
            with SockProt.SockLk:
                SockProt.IsOpen = False
                SockProt.SockCond.notify_all()
            break
        #print "RECEIVED %u" % ord(Str)
        with SockProt.SockLk:
            SockProt.MsgIdRecv = ord(Str)
            SockProt.SockCond.notify_all()
            SockProt.SockCond.wait()


def ReplShell(terminal, globs, locs, ps1, ps2):
    use_locals = True
    while True:
        # noinspection PyBroadException
        try:
            inp = terminal.ReadLine(ps1)
            inp1 = inp
            while inp1.startswith(" ") or inp1.startswith("\t") or inp1.endswith(":"):
                inp1 = terminal.ReadLine(ps2)
                inp += "\n" + inp1
            if len(inp) == 0:
                continue
            elif inp.startswith("#"):
                lower = inp.lower()
                str0 = "#use-locals "
                str1 = "#exit-cur-repl"
                if lower.startswith(str0):
                    use_locals = int(inp[len(str0):])
                elif lower.startswith(str1):
                    break
            output = None
            try:
                output = eval(inp, globs, locs if use_locals else globs)
            except SyntaxError:
                exec(inp, globs, locs if use_locals else globs)
            if output is not None:
                terminal.WriteLk(repr(output))
        except:
            terminal.WriteErrLk(traceback.format_exc())


def DefReplRunner(inp, globs, locs):
    """
    :param str|unicode inp:
    :param dict[str|unicode,any] globs:
    :param dict[str|unicode,any] locs:
    :rtype: (str|unicode, bool)
    """
    try:
        prn = None
        try:
            prn = eval(inp, globs, locs)
        except SyntaxError:
            exec (inp, globs, locs)
        if prn is not None:
            return repr(prn) + "\n", False
    except:
        return traceback.format_exc(), True
    return "", False


def SockRecvAll(sock, num):
    rtn = ""
    while num > 0:
        data = sock.recv(num)
        if len(data) == 0:
            raise socket.error("Connection reset by peer")
        rtn += data
        num -= len(data)
    return rtn


class MsgSockProt(object):
    def __init__(self, Sock):
        self.Sock = Sock
        self.SockLk = threading.Lock()
        self.MsgIdRecv = None
        self.IsOpen = True
        self.SockCond = threading.Condition(self.SockLk)
        self.SockThrd = threading.Thread(
            target=MsgSockThrd, args=(self,),
            name="Socket Thread %s" % str(Sock.getpeername()))
        self.SockThrd.start()
    
    def SendMsg(self, MsgId, Data, HeadSize=2):
        with self.SockLk:
            if not self.IsOpen:
                raise socket.error("attempted action on closed connection")
            self.Sock.sendall(chr(MsgId)+PackStrLen(Data,HeadSize))
            while self.MsgIdRecv is None or self.MsgIdRecv != MsgId:
                self.SockCond.wait()#wait for the dispatcher thread to recv
                if not self.IsOpen: raise socket.error("Connection reset")
            self.MsgIdRecv = None
            str0 = SockRecvAll(self.Sock, HeadSize)
            Len = GetLongStrBytes(str0)
            Rtn = SockRecvAll(self.Sock, Len)
            self.SockCond.notify_all()#back notify the dispatcher thread
            return Rtn
    
    def close(self):
        with self.SockLk:
            self.IsOpen = False
        self.SockThrd.join()


EXIT_TERM = 0
READ_LINE = 1
WRIT_LINE = 2


class SocketTerm(BaseTerm):
    def __init__(self):
        self.Lks = [threading.Lock(), threading.Lock(), threading.Lock()]
        self.SockProt = None
    
    def ReadLine(self, Prompt=""):
        with self.Lks[READ_LINE]:
            return self.SockProt.SendMsg(READ_LINE, Prompt)
    
    def Write(self, Str):
        with self.Lks[WRIT_LINE]:
            self.SockProt.SendMsg(WRIT_LINE, Str)
    
    WriteLk = Write
    
    def Print(self, *args):
        self.Write(" ".join(map(str, args))+"\n")
    
    PrintLk = Print
    
    def ExitTerm(self):
        with self.Lks[EXIT_TERM]:
            self.SockProt.SendMsg(EXIT_TERM, "")


class BareSockTerm(SocketTerm):
    def __init__(self, Sock):
        super(BareSockTerm, self).__init__()
        self.SockProt = MsgSockProt(Sock)


def ReplShell1(term_obj, globs, locs, ps1, ps2, fn=DefReplRunner, fn_is_stop=None):
    """
    
    :param fn_is_stop: 
    :param BaseTerm term_obj:
    :param globs:
    :param locs:
    :param ps1:
    :param ps2:
    :param (str|unicode,dict[str|unicode,any],dict[str|unicode,any]) -> (str|unicode, bool) fn:
    """
    use_locals = True
    while True if fn_is_stop is None else not fn_is_stop():
        inp = term_obj.ReadLine(ps1)
        inp1 = inp
        while inp1.startswith(" ") or inp1.startswith("\t") or inp1.endswith(":"):
            inp1 = term_obj.ReadLine(ps2)
            inp += "\n" + inp1
        if len(inp) == 0:
            continue
        elif inp.startswith("#"):
            lower = inp.lower()
            str0 = "#use-locals "
            str1 = "#exit-cur-repl"
            if lower.startswith(str0):
                use_locals = int(inp[len(str0):])
                continue
            elif lower.startswith(str1):
                break
        prn, is_err = fn(inp, globs, locs if use_locals else globs)
        if is_err:
            term_obj.WriteErrLk(prn)
        else:
            term_obj.WriteLk(prn)