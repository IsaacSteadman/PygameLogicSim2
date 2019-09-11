import sys
sys.path.insert(0, "./PygGUI")
import PygCtl
from PygCtl import pygame, GREEN, RED, BLACK, WHITE
from LogicSim import *
try:
    import TermHelper
except ImportError:
    pass
import Queue
import threading
PygCtl.BKGR = (64,64,64)
BLUE = (0, 0, 255)
CMD_EXIT = 0
CMD_PAUSE = 1
CMD_RESUME = 2

def DiffPos((x0, y0), (x1, y1)):
    return x0 - x1, y0 - y1
def AddPos((x0, y0), (x1, y1)):
    return x0 + x1, y0 + y1
def DivPos((x, y), n):
    return x / n, y / n
def MulPos((x, y), n):
    return x * n, y * n
def WithinPos((x, y), (w, h)):
    return 0 <= x < w and 0 <= y < h
def GetDist((x0, y0), (x1, y1)):
    return ((x0 - x1) ** 2 + (y0 - y1) ** 2) ** .5
def RotateAround(Pos, Center, Rot):
    Rot %= 4
    x, y = DiffPos(Pos, Center)
    if Rot >> 1:
        x, y = -x, -y
    if Rot % 2:
        x, y = -y, x
        #Center = Center[::-1]
    return AddPos(Center, (x, y))
def TestRotate():
    c0 = (2, 2)
    pt0 = (4, 4)
    l0 = 0
    r0 = 4
    t0 = 0
    b0 = 4
    c1 = (24, 14)
    pt1 = (26, 16)
    l1 = 22
    r1 = 26
    t1 = 12
    b1 = 16
    pt1_1 = c1[0], b1
    pt1_2 = r1, c1[1]
    data = [
        (pt0, c0, -2, (l0, t0)),
        (pt0, c0, 2, (l0, t0)),
        (pt0, c0, -1, (r0, t0)),
        (pt0, c0, 1, (l0, b0)),
        (pt0, c0, -3, (l0, b0)),
        (pt0, c0, 3, (r0, t0)),
        (pt1, c1, -2, (l1, t1)),
        (pt1, c1, 2, (l1, t1)),
        (pt1, c1, -1, (r1, t1)),
        (pt1, c1, 1, (l1, b1)),
        (pt1, c1, -3, (l1, b1)),
        (pt1, c1, 3, (r1, t1)),

        (pt1_1, c1, -2, (c1[0], t1)),
        (pt1_1, c1, 2, (c1[0], t1)),
        (pt1_1, c1, -1, (r1, c1[1])),
        (pt1_1, c1, 1, (l1, c1[1])),
        (pt1_1, c1, -3, (l1, c1[1])),
        (pt1_1, c1, 3, (r1, c1[1])),

        (pt1_2, c1, -2, (l1, c1[1])),
        (pt1_2, c1, 2, (l1, c1[1])),
        (pt1_2, c1, -1, (c1[0], t1)),
        (pt1_2, c1, 1, (c1[0], b1)),
        (pt1_2, c1, -3, (c1[0], b1)),
        (pt1_2, c1, 3, (c1[0], t1)),
    ]
    for c, test in enumerate(data):
        (pt, center, rot, expect) = test
        result = RotateAround(pt, center, rot)
        if result != expect:
            print "Failed test #%u data = %r, got %r" % (c, test, result)
        else:
            print "Passed test #%u data = %r" % (c, test)
#TestRotate()

PortColors = [
    WHITE,
    (0xA0, 0xA0, 0xA0),
    BLACK
]

CurPort = None

class Port(PygCtl.PygCtl):
    def __init__(self, parent, portI):
        """
        :param DataBlockView parent:
        :param int|long portI:
        """
        self.parent = parent
        self.portI = portI
        self.Dragging = False
        self.GhostPos = (0, 0)
        self.PrevRect = None
        # the outer #1b1b1b colored band is 2 pixels wide and the inner radius is 3 pixels
        self.OuterR = 5
        self.InnerR = 3
        self.InnerColor = PortColors[parent.DataBlock.ports[portI] + 1]
        self.LstConn = []
        self.OuterColor = (0x1B, 0x1B, 0x1B)
        self.GhostColor = (0, 191, 191, 63)
    def GetPos(self):
        parent = self.parent
        return AddPos(parent.Pos, parent.PortPos[self.portI])
    def OnEvt(self, Evt, Pos):
        global CurPort
        if Evt.type == pygame.MOUSEBUTTONDOWN:
            self.Dragging = True
            self.GhostPos = Pos
            CurPort = self
            return True
        return False
    def OnEvtGlobal(self, Evt):
        global CurPort
        if self.Dragging:
            if Evt.type == pygame.MOUSEMOTION:
                self.GhostPos = Evt.pos
                return True
            elif Evt.type == pygame.MOUSEBUTTONUP:
                self.Dragging = False
                CurPort = None
                return True
        return False
    def Draw(self, Surf):
        Pos = self.GetPos()
        Rtn = [None, None, None] if self.Dragging else [None]
        self.PrevRect = Rtn[0] = pygame.draw.circle(Surf, self.OuterColor, Pos, self.OuterR)
        pygame.draw.circle(Surf, self.InnerColor, Pos, self.InnerR)
        if self.Dragging:
            gPos = self.GhostPos
            gColor = self.GhostColor
            alpha = gColor[3]
            Rtn[1] = pygame.draw.line(Surf, gColor, Pos, gPos, 2)
            Rtn[2] = pygame.draw.circle(Surf, self.OuterColor + (alpha,), gPos, self.OuterR)
            pygame.draw.circle(Surf, self.InnerColor + (alpha,), gPos, self.InnerR)
            self.PrevRect = self.PrevRect.unionall(Rtn[1:])
        return Rtn
    def PreDraw(self, Surf):
        CurRect = self.PrevRect
        if CurRect is None:
            return []
        self.PrevRect = None
        Surf.fill(PygCtl.BKGR, CurRect)
        return [CurRect]
    def CollidePt(self, Pt):
        return GetDist(self.GetPos(), Pt) < self.OuterR


class Drawable(object):
    def Draw(self, Surf, Pos, Rot, Active=False):
        return None
    def GetSize(self, Rot, Active=False):
        return 0, 0
    def GetImg(self, Rot, Active=False):
        Size = self.GetSize(Rot)
        Surf = pygame.Surface(Size)
        self.Draw(Surf, (0, 0), Rot)
        return Surf
class ImageGroup(object):
    def __init__(self, Img):
        self.LstImg = [
            Img,
            pygame.transform.rotate(Img, 270),
            pygame.transform.rotate(Img, 180),
            pygame.transform.rotate(Img, 90),
        ]
class Image(Drawable):
    def __init__(self, ImgGroup):
        """
        :param Image Group ImgGroup:
        """
        self.ImgGroup = ImgGroup
    def Draw(self, Surf, Pos, Rot, Active=False):
        return Surf.blit(self.ImgGroup.LstImg[Rot], Pos)
    def GetSize(self, Rot, Active=False):
        return self.ImgGroup.LstImg[Rot].get_size()
    def GetImg(self, Rot, Active=False):
        return self.ImgGroup.LstImg[Rot]
class DrawRect(Drawable):
    def __init__(self, Colors, Width, Height):
        """
        :param ((int,int,int),(int,int,int)) Colors:
        :param int|long Width:
        :param int|long Height:
        """
        self.Size = (Width, Height)
        self.Colors = Colors
    def Draw(self, Surf, Pos, Rot, Active=False):
        return Surf.fill(
            self.Colors[1 if Active else 0],
            pygame.Rect(Pos, self.Size[::-1] if Rot % 2 else self.Size))
    def GetSize(self, Rot, Active=False):
        return self.Size[::-1] if Rot % 2 else self.Size
class Draw2Rect(Drawable):
    def __init__(self, Colors, Width, Height, iWidth, iHeight):
        """

        :param (((int,int,int),(int,int,int)),((int,int,int),(int,int,int))) Colors:
        :param int|long Width:
        :param int|long Height:
        :param int|long iWidth:
        :param int|long iHeight:
        """
        assert Width >= iWidth, "Width must be  >= inner Width"
        assert Height >= iHeight, "Height must be >= inner Height"
        self.Size = (Width, Height)
        self.iSize = (iWidth, iHeight)
        self.iOff = (Width - iWidth) / 2, (Height - iHeight) / 2
        self.Colors = Colors
    def Draw(self, Surf, Pos, Rot, Active=False):
        Color, iColor = self.Colors[1 if Active else 0]
        Size, iSize, iOff = (
            (self.Size[::-1], self.iSize[::-1], self.iOff[::-1])
            if Rot % 2 else
            (self.Size, self.iSize, self.iOff))
        iPos = AddPos(Pos, iOff)
        Rtn = Surf.fill(Color, pygame.Rect(Pos, Size))
        Surf.fill(iColor, pygame.Rect(iPos, iSize))
        return Rtn
    def GetSize(self, Rot, Active=False):
        return self.Size[::-1] if Rot % 2 else self.Size


BLK_INP = 0
BLK_OUTP = 1
BLK_HYBP = 2
BLK_NOT = 3
BLK_OR = 4
BLK_AND = 5
BLK_NOR = 6
BLK_NAND = 7
BLK_XOR = 8
BLK_XNOR = 9

AREA_REL_C = 0

DataBlocks = [
    (InpNode, [(0.0, 0.5)], True, None),
    (OutNode, [(1.0, 0.5)], True, (AREA_REL_C, 0.5)),
    (HybNode, [(0.5, 0.0)], True, (AREA_REL_C, 0.5)),
    (NotGate, [(0.0, 0.5), (1.0, 0.5)], False, None),
    (OrGate, [(0.0, 0.25), (0.0, 0.75), (1.0, 0.5)], False, None),
    (AndGate, [(0.0, 0.25), (0.0, 0.75), (1.0, 0.5)], False, None),
    (NorGate, [(0.0, 0.25), (0.0, 0.75), (1.0, 0.5)], False, None),
    (NandGate, [(0.0, 0.25), (0.0, 0.75), (1.0, 0.5)], False, None),
    (XorGate, [(0.0, 0.25), (0.0, 0.75), (1.0, 0.5)], False, None),
    (XnorGate, [(0.0, 0.25), (0.0, 0.75), (1.0, 0.5)], False, None)
]

dbg_ui_msg = False

class DataBlockView(PygCtl.PygCtl):
    def __init__(self, DataBlock, Pos, PortPos, DrawObj, ActionArea):
        """
        :param DataGateBlock DataBlock:
        :param (int|long, int|long) Pos:
        :param list[(float, float)] PortPos:
        :param Drawable DrawObj:
        :param (int|long, float)|None ActionArea:
        """
        self.Dragging = False
        self.DragOff = (0, 0)
        self.DataBlock = DataBlock
        self.Pos = Pos
        Size = DrawObj.GetSize(0)
        assert Size is not None
        w, h = Size
        self.BasePortPos = [
            (int(x * w), int(y * h))
            for x, y in PortPos
        ]
        self.PortPos = self.BasePortPos
        self.DrawObj = DrawObj
        self.Active = False
        self.ActionArea = ActionArea
        self.ActionActive = False
        self.Rot = 0
        self.Ports = [Port(self, x) for x in xrange(len(PortPos))]
        self.PrevRect = None
    def Rotate(self, Dir):
        Rot = self.Rot
        Size = self.DrawObj.GetSize(0)
        Dir %= 4
        Center = DivPos(Size, 2)
        Center1 = Center[::-1] if Rot % 2 else Center
        Rot = (Rot + Dir) % 4
        Off = DiffPos(Center1[::-1], Center1) if Dir % 2 or Rot % 2 else (0, 0)
        PosOff = Off if Dir % 2 else (0, 0)
        PortOff = Off if Rot % 2 else (0, 0)
        self.PortPos = [
            AddPos(RotateAround(pPos, Center, Rot), PortOff)
            for pPos in self.BasePortPos
        ]
        #print "Center = %r, Size = %r, AbsCenter = %r, PortPos = %r" % (Center1, Size, AddPos(Pos, Center1), self.PortPos)
        self.Pos = DiffPos(self.Pos, PosOff)
        self.Rot = Rot
    def Draw(self, Surf):
        self.PrevRect = self.DrawObj.Draw(Surf, self.Pos, self.Rot, self.Active)
        return [self.PrevRect]
    def PreDraw(self, Surf):
        if self.PrevRect is None: return []
        CurRect = self.PrevRect
        self.PrevRect = None
        return [Surf.fill(PygCtl.BKGR, CurRect)]
    def OnEvt(self, Evt, Pos):
        if Evt.type == pygame.MOUSEBUTTONDOWN:
            if Evt.button != 1:
                return False
            ActionArea = self.ActionArea
            if ActionArea is not None:
                assert ActionArea[0] == AREA_REL_C
                RelSz = ActionArea[1]
                Size = self.DrawObj.GetSize(self.Rot, self.Active)
                aSize = MulPos(Size, RelSz)
                aOff = DivPos(DiffPos(Size, aSize), 2)
                theCmp = DiffPos(DiffPos(Pos, self.Pos), aOff)
                if WithinPos(theCmp, aSize):
                    #print "ACTION!!!"
                    DataBlock = self.DataBlock
                    if self.ActionActive:
                        self.ActionActive = False
                        DataBlock.data[0] = 0
                    else:
                        self.ActionActive = True
                        DataBlock.data[0] = 2
                    DataBlock.dirty = True
                    return True
                #print "NO_ACTION: theCmp = %r, Pos = %r, self.Pos = %r, aOff = %r, ActionArea = %r, aSize = %r" % (
                #    theCmp, Pos, self.Pos, aOff, ActionArea, aSize)
            self.Dragging = True
            self.DragOff = DiffPos(Pos, self.Pos)
            return True
        elif Evt.type == pygame.KEYDOWN:
            if Evt.key == pygame.K_r:
                self.Rotate(-1 if Evt.mod & pygame.KMOD_SHIFT else 1)
                PygCtl.SetListRedraw(self.Ports)
                return True
        return False
    def OnEvtGlobal(self, Evt):
        if self.Dragging:
            if Evt.type == pygame.MOUSEMOTION:
                self.Pos = DiffPos(Evt.pos, self.DragOff)
                PygCtl.SetListRedraw(self.Ports)
                for p in self.Ports:
                    PygCtl.SetListRedraw(p.LstConn)
                return True
            elif Evt.type == pygame.MOUSEBUTTONUP:
                self.Dragging = False
        return False
    def OnMouseEnter(self):
        return False
    def OnMouseExit(self):
        return False
    def CollidePt(self, Pt):
        return WithinPos(DiffPos(Pt, self.Pos), self.DrawObj.GetSize(self.Rot))
    def OnChangeData(self, DataBlock):
        """
        :param DataGateBlock DataBlock:
        """
        NewV = bool(DataBlock.data[-1])
        if dbg_ui_msg:
            print "HELLO ChangeData(self=%r, DataBlock=%r" % (self, DataBlock)
        if self.Active != NewV:
            self.Active = NewV
            PygCtl.SetRedraw(self)
            if dbg_ui_msg:
                print "DUDE: Change %r" % self.Active


# This factory actually has a user drag-n-drop interface
class DataBlockFactory(PygCtl.PygCtl):
    def __init__(self, Pos, BlkType, DrawObj, App):
        """
        :param (int|long, int|long) Pos:
        :param int|long BlkType:
        :param Drawable DrawObj:
        :param AppClass App:
        """
        self.Pos = Pos
        self.BlkType = BlkType
        self.DrawObj = DrawObj
        self.Img = DrawObj.GetImg(0)
        self.gImg = self.Img.copy()
        self.gImg.set_alpha(127)
        self.Dragging = False
        self.gPos = (0, 0)
        self.DragOff = (0, 0)
        self.PrevRect = None
        self.App = App
    def Draw(self, Surf):
        Rtn = [None] * (1 + int(self.Dragging))
        self.PrevRect = Rtn[0] = Surf.blit(self.Img, self.Pos)
        if len(Rtn) >= 2:
            Rtn[1] = Surf.blit(self.gImg, self.gPos)
            self.PrevRect = self.PrevRect.union(Rtn[1])
        return Rtn
    def PreDraw(self, Surf):
        if self.PrevRect is None: return []
        CurRect = self.PrevRect
        self.PrevRect = None
        return [Surf.fill(PygCtl.BKGR, CurRect)]
    def OnEvt(self, Evt, Pos):
        if Evt.type == pygame.MOUSEBUTTONDOWN:
            if Evt.button == 1:
                self.Dragging = True
                self.DragOff = DiffPos(Pos, self.Pos)
                self.gPos = self.Pos
                return True
        return False
    def OnEvtGlobal(self, Evt):
        if self.Dragging:
            if Evt.type == pygame.MOUSEMOTION:
                self.gPos = DiffPos(Evt.pos, self.DragOff)
                return True
            elif Evt.type == pygame.MOUSEBUTTONUP and Evt.button == 1:
                if not self.CollidePt(Evt.pos):
                    self.CreateBlock(self.gPos)
                self.Dragging = False
                return True
        return False
    def CreateBlock(self, Pos):
        BlkType = self.BlkType
        Cls, PortPos, BindData, ActArea = DataBlocks[BlkType]
        DataBlk = Cls()
        """ :type: DataGateBlock """
        Blk = DataBlockView(DataBlk, Pos, PortPos, self.DrawObj, ActArea)
        if BindData:
            DataBlk.extData = (DataBlockView.OnChangeData, Blk)
            if dbg_ui_msg:
                print "Binding"
            # TODO: Output blocks work but hybrid blocks dont, and output is not propagated from output block
        AddBlock(Blk, self.App)
    def OnMouseEnter(self):
        return False
    def OnMouseExit(self):
        return False
    def CollidePt(self, Pt):
        return WithinPos(DiffPos(Pt, self.Pos), self.Img.get_size())

def SetListI(lst, i, v, fill):
    """
    :param list[T] lst:
    :param int|long i:
    :param T v:
    :param T fill:
    """
    n = len(lst)
    if n <= i:
        lst[n:i + 1] = [fill] * (1 + i - n)
    lst[i] = v

CONN_COLORS = (RED, GREEN)

class DataConnViewNode(PygCtl.PygCtl):
    def __init__(self, DataConn, Pos):
        """
        :param DataConnection DataConn:
        :param (int|long, int|long) Pos:
        """
        # TODO: DataConnection use a sorted list and do binary search for
        self.DataConn = DataConn
        self.Pos = Pos
        self.NodeR = 15
        self.Active = False
        self.PrevRect = None
        self.Dragging = False
        self.DragOff = (0, 0)
        self.LstConn = []
        DataConn.extData = (DataConnViewNode.OnChangeData, self)

    def Draw(self, Surf):
        self.PrevRect = pygame.draw.circle(Surf, CONN_COLORS[int(self.Active)], self.Pos, self.NodeR)
        return [self.PrevRect]

    def CollidePt(self, Pt):
        return GetDist(Pt, self.Pos) <= self.NodeR

    def OnEvt(self, Evt, Pos):
        global CurPort
        if Evt.type == pygame.MOUSEBUTTONUP:
            if Evt.button == 1 and CurPort is not None and CurPort.Dragging:
                self.Connect(CurPort)
        elif Evt.type == pygame.MOUSEBUTTONDOWN:
            if Evt.button == 1:
                self.Dragging = True
                self.DragOff = DiffPos(Pos, self.Pos)
        elif Evt.type == pygame.KEYDOWN and Evt.key == pygame.K_DELETE:
            App = AppClass.LstApps[0]
            assert isinstance(App, AppClass)
            App.main_group.removeConn(self.DataConn)
            PygCtl.LstCtl.remove(self)
            return True
        return False

    def Connect(self, port):
        """
        :param Port port:
        """
        App = AppClass.LstApps[0]
        wire = DataWire(self, port)
        port.LstConn.append(wire)
        self.LstConn.append(wire)
        blkI = App.main_group.blocks.index(port.parent.DataBlock)
        self.DataConn.addPort(blkI, port.portI)
        PygCtl.LstCtl.append(wire)
        PygCtl.SetRedraw(wire)

    def PreDraw(self, Surf):
        if self.PrevRect is None: return []
        CurRect = self.PrevRect
        self.PrevRect = None
        return [Surf.fill(PygCtl.BKGR, CurRect)]

    def OnMouseExit(self):
        return super(DataConnViewNode, self).OnMouseExit()

    def OnEvtGlobal(self, Evt):
        if self.Dragging:
            if Evt.type == pygame.MOUSEMOTION:
                self.Pos = DiffPos(Evt.pos, self.DragOff)
                PygCtl.SetListRedraw(self.LstConn)
                return True
            elif Evt.type == pygame.MOUSEBUTTONUP and Evt.button == 1:
                self.Dragging = False
        return False

    def OnMouseEnter(self):
        return super(DataConnViewNode, self).OnMouseEnter()

    def OnChangeData(self, DataConn):
        """
        :param DataConnection DataConn:
        """
        NewV = bool(DataConn.isOn)
        if self.Active != NewV:
            self.Active = NewV
            PygCtl.SetRedraw(self)

DATA_WIRE_COLOR = (0x7F, 0x7F, 0x7F)

class DataWire(PygCtl.PygCtl):
    def __init__(self, node, port):
        """
        :param DataConnViewNode node:
        :param Port port:
        """
        self.node = node
        self.port = port
        self.Width = 2
        self.Glow = False
        self.PrevRect = None
    def Delete(self, App):
        """
        :param AppClass App:
        """
        portI = self.port.portI
        blk = self.port.parent.DataBlock
        # FIXME: I cant shake the feeling that this call is really inefficient
        blkI = App.main_group.blocks.index(blk)
        self.node.DataConn.remPort(blkI, portI)
        self.port.LstConn.remove(self)
        self.node.LstConn.remove(self)
        PygCtl.LstCtl.remove(self)
        PygCtl.SetRedraw(self)

    def Draw(self, Surf):
        self.PrevRect = pygame.draw.line(Surf, DATA_WIRE_COLOR, self.port.GetPos(), self.node.Pos, self.Width + int(self.Glow))
        return [self.PrevRect]

    def CollidePt(self, Pt):
        return PygCtl.CollideLineWidth(Pt, self.port.GetPos(), self.node.Pos, self.Width + 1)

    def OnEvt(self, Evt, Pos):
        if Evt.type == pygame.KEYDOWN and Evt.key == pygame.K_DELETE:
            self.Delete(AppClass.LstApps[0])

    def PreDraw(self, Surf):
        CurRect = self.PrevRect
        if CurRect is None:
            return []
        self.PrevRect = None
        return [Surf.fill(PygCtl.BKGR, CurRect)]

    def OnMouseExit(self):
        self.Glow = False
        return True

    def OnMouseEnter(self):
        self.Glow = True
        return True

class DataConnView(PygCtl.PygCtl):
    """
    :type PointMembers: list[list[int|long]]
    :type Points: list[(int|long, int|long)]
    :type Glow: bool
    :type Width: int|long
    :type GlowWidth: int|long
    :type mWidth: int|long
    :type DataConn: DataConnection
    :type Active: bool
    :type MemberPorts: list[Port]
    """

    def __init__(self, DataConn, Points):
        """
        :param DataConnection DataConn:
        :param list[(int|long, int|long)] Points:
        """
        self.DataConn = DataConn
        self.Active = False
        self.MemberPorts = []
        DataConn.extData = (DataConnView.OnChangeConn, self)
        self.Glow = False
        self.Width = 1
        self.GlowWidth = 2
        self.mWidth = 5
        self.Points = []
        self.PointMembers = []
        self.PrevRect = None
        self.DragPtI = None
        self.DragOff = (0, 0)

    def Draw(self, Surf):
        Color = CONN_COLORS[1 if self.Active else 0]
        Width = self.GlowWidth if self.Glow else self.Width
        self.PrevRect = pygame.draw.lines(Surf, Color, False, self.Points, Width)
        Rtn = [self.PrevRect]
        for c, Pt in enumerate(self.Points):
            PortIndices = self.PointMembers[c]
            for PortI in PortIndices:
                ThePort = self.MemberPorts[PortI]
                Rtn.append(pygame.draw.line(Surf, Color, Pt, ThePort.GetPos()))
        self.PrevRect = self.PrevRect.unionall(Rtn[1:])
        return Rtn

    def CollidePt(self, Pt):
        Points = self.Points
        PointMembers = self.PointMembers
        if len(self.Points) < 1: return False
        for c in xrange(len(self.Points) - 1):
            if PygCtl.CollideLineWidth(Pt, self.Points[c], self.Points[c + 1], self.mWidth):
                return True
            for PortI in PointMembers[c]:
                ThePort = self.MemberPorts[PortI]
                if PygCtl.CollideLineWidth(Pt, self.Points[c], ThePort.GetPos(), self.mWidth):
                    return True
        for PortI in PointMembers[-1]:
            ThePort = self.MemberPorts[PortI]
            if PygCtl.CollideLineWidth(Pt, self.Points[-1], ThePort.GetPos(), self.mWidth):
                return True
        return False

    def OnEvt(self, Evt, Pos):
        if Evt.type == pygame.MOUSEBUTTONDOWN:
            if Evt.button in [1, 3]:
                Min = (0, GetDist(self.Points[0], Pos))
                for c, Pt in enumerate(self.Points):
                    d = GetDist(Pt, Pos)
                    if Min[1] > d:
                        Min = c, d
                if Evt.button == 1:
                    self.DragPtI = Min[0]
                elif len(self.Points) > 1:
                    pass

    def PreDraw(self, Surf):
        if self.PrevRect is None: return []
        CurRect = self.PrevRect
        self.PrevRect = None
        return [Surf.fill(PygCtl.BKGR, CurRect)]

    def OnMouseExit(self):
        self.Glow = False
        return True

    def OnEvtGlobal(self, Evt):
        if self.DragPtI is not None:
            if Evt.type == pygame.MOUSEMOTION:
                self.Points[self.DragPtI] = DiffPos(Evt.pos, self.DragOff)
                return True
            elif Evt.type == pygame.MOUSEBUTTONUP and Evt.button == 1:
                self.DragPtI = None
                return True
        return False

    def OnMouseEnter(self):
        self.Glow = True
        return True

    def OnChangeConn(self, conn):
        """
        :param DataConnection conn:
        """
        self.Active = conn.isOn
        PygCtl.SetRedraw(self)


def AddBlock(Blk, App):
    """
    :param DataBlockView Blk:
    :param AppClass App:
    """
    PygCtl.LstCtl.append(Blk)
    PygCtl.LstCtl.extend(Blk.Ports)
    App.main_group.blocks.append(Blk.DataBlock)
    PygCtl.SetListRedraw([Blk] + Blk.Ports)
REMOVE_EMPTY_CONN = False
def RemBlock(Blk, App):
    """
    :param DataBlockView Blk:
    :param AppClass App:
    """
    LstCtl = PygCtl.LstCtl
    Pos = LstCtl.index(Blk)
    LstCtlC = Pos + 1
    PortC = 0
    nCtl = len(LstCtl)
    NewLst = [None] * len(LstCtl)
    NewLst[:Pos] = LstCtl[:Pos]
    NewC = Pos
    Ports = Blk.Ports
    nPorts = len(Ports)
    while LstCtlC < nCtl and PortC < nPorts:
        if Ports[PortC] is LstCtl[LstCtlC]:
            PortC += 1
            LstCtlC += 1
        else:
            NewLst[NewC] = LstCtl[LstCtlC]
            NewC += 1
            LstCtlC += 1
    NewLst[NewC:] = []
    LstCtl[:LstCtlC] = NewLst
    Pos = App.main_group.blocks.index(Blk)
    if not REMOVE_EMPTY_CONN: return
    toRemove = []
    for c, conn in enumerate(App.main_group.connections):
        conn.members = [(blkI if blkI < Pos else blkI - 1, portI) for blkI, portI in conn.members if blkI != Pos]
        if len(conn.members) == 0:
            toRemove.insert(0, c)
    if len(toRemove):
        for c in toRemove:
            RemConn(App.main_group.connections[c].extData[1], App)
        oldConn = App.main_group.connections
        toRemove.reverse()
        nR = len(toRemove)
        n = len(oldConn)
        newConn = App.main_group.connections = [None] * (n - nR)
        c = 0
        cR = 0
        while cR < nR and c < n:
            while c < toRemove[cR]:
                newConn[c - cR] = oldConn[c]
                c += 1
            cR += 1
            c += 1
def RemConn(Conn, App):
    """
    :param DataConnView Conn:
    :param AppClass App:
    """



class DataBlockGroupManager(object):
    """
    :type DataGroup: DataBlockGroup
    :type CmdQueue: Queue.Queue
    :type paused: bool
    :type TimeStep: float|int|long
    """
    __slots__ = ["DataGroup", "CmdQueue", "paused", "running", "TimeStep"]
    def __init__(self, DataGroup):
        self.DataGroup = DataGroup
        self.CmdQueue = Queue.Queue()
        self.paused = False
        self.running = False
        self.TimeStep = 1.0
    def Run(self):
        if self.running:
            return
        CmdQueue = self.CmdQueue
        self.running = True
        cmd = None
        while True:
            cmd = None
            try:
                cmd = CmdQueue.get() if self.paused else CmdQueue.get(True, self.TimeStep)
                if cmd is None:
                    CmdQueue.task_done()
            except Queue.Empty:
                pass
            if cmd is not None:
                if cmd == CMD_PAUSE:
                    self.paused = True
                elif cmd == CMD_RESUME:
                    self.paused = False
                elif cmd == CMD_EXIT:
                    CmdQueue.task_done()
                    self.running = False
                    break
                CmdQueue.task_done()
            if not self.paused:
                self.DataGroup.Step()
    def Pause(self):
        self.CmdQueue.put(CMD_PAUSE)
        self.CmdQueue.join()
    def Resume(self):
        self.CmdQueue.put(CMD_RESUME)
        self.CmdQueue.join()
    def Exit(self):
        if self.running:
            self.Resume()
            self.CmdQueue.put(CMD_EXIT)
            self.CmdQueue.join()

def Main():
    main_group = DataBlockGroup()
    interface = BoundData()
    interface.allocItems(2)
    main_group.blocks = [
        OutNode(), # 0
        AndGate(), # 1
        NotGate(), # 2
        InpNode() # 3
    ]
    main_group.connections = [
        DataConnection([
            (0, 0), (1, 0)
        ]),
        DataConnection([
            (1, 2), (2, 0)
        ]),
        DataConnection([
            (2, 1), (1, 1)
        ]),
        DataConnection([
            (1, 2), (3, 0)
        ])
    ]
    interface.watchItem(0, main_group.blocks[0])
    main_group.blocks[3].extData = (BoundData.changeData, (interface, 1))
    manager = DataBlockGroupManager(main_group)
    term = TermHelper.CmdTerm()
    interface.reporter = lambda txt: term.WriteLk(txt)
    Thrd = threading.Thread(target=DataBlockGroupManager.Run, args=(manager,), name="Sim Thread")
    manager.paused = True
    Thrd.start()
    TermHelper.ReplShell(term, globals(), locals(), ">>> ", "... ")
    term.WriteLk("Exiting\n")
    manager.Exit()
    Thrd.join()
    term.WriteLk("Done Exiting\n")
    return term, main_group, interface

class AppClass(object):
    LstApps = []
    @classmethod
    def AddApp(cls, App):
        cls.LstApps.append(App)
    @classmethod
    def RemApp(cls, App):
        cls.LstApps.remove(App)
    def __init__(self):
        self.main_group = DataBlockGroup()
        self.manager = DataBlockGroupManager(self.main_group)
        self.auto_step = False
        self.cur_step_freq = 0
        i = pygame.USEREVENT
        while i in PygCtl.DctEvtFunc:
            i += 1
        self.step_evt_id = i
        PygCtl.DctEvtFunc[i] = lambda evt: self.main_group.Step()
    def set_auto_step(self, freq):
        assert freq >= 0
        if freq == 0:
            self.auto_step = False
            pygame.time.set_timer(self.step_evt_id, 0)
        else:
            self.auto_step = True
            pygame.time.set_timer(self.step_evt_id, int(1e3 / freq))
        self.cur_step_freq = freq
    def NewConnNode(self):
        Surf = pygame.display.get_surface()
        Pos = DivPos(Surf.get_size(), 2)
        Conn = DataConnection([])
        self.main_group.connections.append(Conn)
        WidConn = DataConnViewNode(Conn, Pos)
        PygCtl.LstCtl.append(WidConn)
        PygCtl.SetRedraw(WidConn)


def get_next_unallocated():
    i = pygame.USEREVENT
    while i in PygCtl.DctEvtFunc:
        i += 1
    return i


ATTACH_REPL_LISTENER = True


def Main1():
    PygCtl.Init()
    App = AppClass()
    AppClass.AddApp(App)
    lstDraw = []
    TxtFnt = pygame.font.SysFont("courier new", 40)
    fill = Image(ImageGroup(TxtFnt.render("ERROR", False, RED, BLUE)))
    SetListI(lstDraw, BLK_XNOR, Image(ImageGroup(TxtFnt.render("XNOR", False, GREEN, BLUE))), fill)
    SetListI(lstDraw, BLK_NOR, Image(ImageGroup(TxtFnt.render("NOR", False, GREEN, BLUE))), fill)
    SetListI(lstDraw, BLK_XOR, Image(ImageGroup(TxtFnt.render("XOR", False, GREEN, BLUE))), fill)
    SetListI(lstDraw, BLK_OR, Image(ImageGroup(TxtFnt.render("OR", False, GREEN, BLUE))), fill)
    SetListI(lstDraw, BLK_AND, Image(ImageGroup(TxtFnt.render("AND", False, GREEN, BLUE))), fill)
    SetListI(lstDraw, BLK_NAND, Image(ImageGroup(TxtFnt.render("NAND", False, GREEN, BLUE))), fill)
    SetListI(lstDraw, BLK_NOT, Image(ImageGroup(TxtFnt.render("NOT", False, GREEN, BLUE))), fill)
    SetListI(lstDraw, BLK_INP, DrawRect((RED, GREEN), 64, 64), fill)
    ClkImg = Draw2Rect(((RED, BLACK), (GREEN, BLACK)), 64, 64, 32, 32)
    SetListI(lstDraw, BLK_OUTP, ClkImg, fill)
    SetListI(lstDraw, BLK_HYBP, ClkImg, fill)
    lstFactories = [None] * len(lstDraw)
    Pos = [0, 32]
    for c, DrawObj in enumerate(lstDraw):
        obj = DataBlockFactory((Pos[0], Pos[1]), c, DrawObj, App)
        Pos[1] += obj.Img.get_height() + 2
        lstFactories[c] = obj
    PygCtl.LstCtl.extend(lstFactories)
    PygCtl.LstCtl.append(PygCtl.PressBtn("Step", lambda Btn, Pos1: App.main_group.Step(), tuple(Pos), TxtFnt))
    Pos[1] = PygCtl.LstCtl[-1].TotRect.bottom + 2
    PygCtl.LstCtl.append(PygCtl.PressBtn("New Node", lambda Rtn, Pos1: App.NewConnNode(), tuple(Pos), TxtFnt))
    Pos[1] = PygCtl.LstCtl[-1].TotRect.bottom + 2
    PygCtl.LstCtl.append(PygCtl.PressBtn("Auto", lambda Rtn, Pos1: (App.set_auto_step(0) if App.auto_step else App.set_auto_step(20)), tuple(Pos), TxtFnt))
    if ATTACH_REPL_LISTENER:
        import PygCtlRepl
        repl_inst = PygCtlRepl.PygReplInst(get_next_unallocated())
        repl_app = PygCtlRepl.ReplApp(repl_inst)
        repl_app.attach_to_pyg_ctl(PygCtlRepl.OR_NONE)
        # PygCtlRepl.socket.gethostname()
        lst_socks = repl_app.pre_start("localhost", 2500)
        print "Listening on %s" % ", ".join(map(lambda (sock, addr): repr(sock.getsockname()), lst_socks))
        locs = locals()
        def get_locals():
            r = {}
            r.update(locs)
            return r
        repl_app.start(lst_socks, globals(), get_locals)
        PygCtl.RunCtls()
        repl_app.exit()
    else:
        PygCtl.RunCtls()
    App.manager.Exit()
    pygame.quit()

Main1()

# TO USE the REPL shell type the following into command prompt
# cd /D E:/Isaac/devel/ReFiSys
# C:/Python27/python ./TermHelper.py --sock-term 127.0.0.1:2500
