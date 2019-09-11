# from AlgoUtils import *


dbg_step_msg = False


class DataGateBlock(object):
    """
    :type ports: list[int]
    :type data: list[int]
    :type dirty: bool
    :type extData: ((T, DataGateBlock) -> None, T)|None
    """
    __slots__ = ["ports", "data", "dirty", "extData"]

    def __init__(self, Ports, Data, ExtData=None):
        """
        :param list[int] Ports:
        :param list[int] Data:
        :param any ExtData:
        """
        self.ports = Ports
        self.data = Data
        self.dirty = False
        self.extData = ExtData

    def Eval(self):
        raise NotImplementedError("Not Implemented")


class DataConnection(object):
    """
    :type members: list[(int, int)]
    :type isOn: bool
    :type extData: ((T, DataConnection) -> None, T)|None
    """
    __slots__ = ["members", "isOn", "extData"]

    def __init__(self, Members):
        """
        :param list[(int, int)] Members:
        """
        self.members = Members
        self.isOn = False
        self.extData = None

    def addPort(self, blkI, portI):  # TODO: use a sorted list and do binary search
        """
        :param int blkI:
        :param int portI:
        """
        self.members.append((blkI, portI))

    def remPort(self, blkI, portI):
        """
        :param int blkI:
        :param int portI:
        :rtype: bool
        """
        try:
            self.members.remove((blkI, portI))
            return True
        except ValueError:
            return False

    def on_remove(self, group):
        """
        :param DataBlockGroup group:
        """
        for blkI, portI in self.members:
            blk = group.blocks[blkI]
            if blk.ports[portI] > 0:
                continue
            if blk.data[portI] == 1:
                blk.data[portI] = 0
                blk.dirty = True

    def update(self, group):
        """
        :param DataBlockGroup group:
        """
        # print "DO Update"
        newIsOn = False
        for blkI, portI in self.members:
            blk = group.blocks[blkI]
            if blk.ports[portI] < 0:
                if dbg_step_msg:
                    print "Skipped input port: blkI = %u, portI = %u, blk = %r" % (blkI, portI, blk)
                continue
            if blk.data[portI] == 2:
                newIsOn = True
                break
            if dbg_step_msg:
                print "Skipped input port: blkI = %u, portI = %u, blk = %r" % (blkI, portI, blk)
        if newIsOn == self.isOn:
            if dbg_step_msg:
                print "Connection Skipped: already isOn = " + repr(newIsOn)
            return
        self.isOn = newIsOn
        newV = int(newIsOn)
        for blkI, portI in self.members:
            blk = group.blocks[blkI]
            if blk.ports[portI] > 0: continue
            val = blk.data[portI]
            if val == 2 or val == newV: continue
            blk.data[portI] = newV
            blk.dirty = True
        if self.extData is None:
            print "Skip ExtData"
            return
        fn, data = self.extData
        fn(data, self)

# extData is (fn, data)
#   fn is function(dat: is data, blk: DataGateBlock) -> None


class InpNode(DataGateBlock):
    def __init__(self):
        super(InpNode, self).__init__([-1], [0])

    def Eval(self):
        if self.dirty:
            if self.extData is not None:
                fn, dat = self.extData
                fn(dat, self)
            self.dirty = False


class OutNode(DataGateBlock):
    def __init__(self):
        super(OutNode, self).__init__([1], [0])

    def Eval(self):
        if self.dirty:
            if self.extData is not None:
                fn, dat = self.extData
                fn(dat, self)
            self.dirty = False


class HybNode(DataGateBlock):
    def __init__(self):
        super(HybNode, self).__init__([0], [0])

    def Eval(self):
        if self.dirty:
            if self.extData is not None:
                fn, dat = self.extData
                fn(dat, self)
            self.dirty = False


class NotGate(DataGateBlock):
    def __init__(self):
        super(NotGate, self).__init__([-1, 1], [0, 2])

    def Eval(self):
        self.data[1] = 0 if self.data[0] else 2
        self.dirty = False


class OrGate(DataGateBlock):
    def __init__(self):
        super(OrGate, self).__init__([-1, -1, 1], [0, 0, 0])

    def Eval(self):
        self.data[2] = 2 if self.data[0] or self.data[1] else 0
        self.dirty = False


class AndGate(DataGateBlock):
    def __init__(self):
        super(AndGate, self).__init__([-1, -1, 1], [0, 0, 0])

    def Eval(self):
        self.data[2] = 2 if self.data[0] and self.data[1] else 0
        self.dirty = False


class NorGate(DataGateBlock):
    def __init__(self):
        super(NorGate, self).__init__([-1, -1, 1], [0, 0, 2])

    def Eval(self):
        self.data[2] = 0 if self.data[0] or self.data[1] else 2
        self.dirty = False


class NandGate(DataGateBlock):
    def __init__(self):
        super(NandGate, self).__init__([-1, -1, 1], [0, 0, 2])

    def Eval(self):
        self.data[2] = 0 if self.data[0] and self.data[1] else 2
        self.dirty = False


class XorGate(DataGateBlock):
    def __init__(self):
        super(XorGate, self).__init__([-1, -1, 1], [0, 0, 0])

    def Eval(self):
        self.data[2] = 2 if bool(self.data[0]) ^ bool(self.data[1]) else 0
        self.dirty = False


class XnorGate(DataGateBlock):
    def __init__(self):
        super(XnorGate, self).__init__([-1, -1, 1], [0, 0, 2])

    def Eval(self):
        self.data[2] = 0 if bool(self.data[0]) ^ bool(self.data[1]) else 2
        self.dirty = False

class BoundData(object):
    """
    :type data: list[int]
    :type watching: list[DataGateBlock|None]
    :type reporter: ((str|unicode) -> any)|None
    """
    __slots__ = ["data", "watching", "reporter"]

    def __init__(self):
        self.data = []
        self.watching = []
        self.reporter = None

    def allocItems(self, n):
        self.data = [0] * n
        self.watching = [None] * n

    @staticmethod
    def changeData(data, blk):
        """
        :param (BoundData, int|long) data:
        :param DataGateBlock blk:
        """
        self, index = data
        if self.data[index] == 2:
            blk.data[0] = 2
        else:
            self.data[index] = blk.data[0]

    def watchItem(self, i, dataGateBlock):
        """
        :param int|long i:
        :param DataGateBlock dataGateBlock:
        """
        self.watching[i] = dataGateBlock

    def __setitem__(self, i, v):
        watch = self.watching[i]
        self.data[i] = v
        if watch is None:
            if self.reporter is not None:
                self.reporter("CHANGED: i = %u, v = %r\n" % (i, v))
            return
        if watch.data[0] != v:
            watch.data[0] = v
            watch.dirty = True

    def __getitem__(self, i):
        return self.data[i]

    def __len__(self):
        return len(self.data)

class DataBlockGroup(object):
    """
    :type blocks: list[DataGateBlock]
    :type connections: list[DataConnection]
    """
    __slots__ = ["blocks", "connections"]

    def __init__(self):
        self.blocks = []
        self.connections = []

    def Step(self):
        # print "Blocks: " + repr(self.blocks)
        for blk in self.blocks:
            if blk.dirty:
                blk.Eval()
        for conn in self.connections:
            conn.update(self)

    def removeConn(self, Conn):
        """
        :param DataConnection Conn:
        """
        Conn.on_remove(self)
