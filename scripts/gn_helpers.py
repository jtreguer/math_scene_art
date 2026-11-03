"""Small helpers for building Geometry Nodes trees from Python.

Usage inside Blender:
    exec(open(bpy.path.abspath('//scripts/gn_helpers.py')).read())
"""
import bpy


def sock(sockets, key):
    """Socket by index, or by name preferring an enabled one.

    Nodes such as Random Value keep one hidden socket per data type under the
    same name, so a plain sockets[name] can return a disabled socket.
    """
    if isinstance(key, int):
        return sockets[key]
    for s in sockets:
        if s.name == key and s.enabled:
            return s
    return sockets[key]


class Tree:
    """Thin wrapper over a node tree: create nodes, wire them, do math."""

    def __init__(self, name, kind='GeometryNodeTree'):
        ng = bpy.data.node_groups.get(name) or bpy.data.node_groups.new(name, kind)
        ng.nodes.clear()
        ng.interface.clear()
        self.ng = ng
        self.n_in = ng.nodes.new('NodeGroupInput')
        self.n_out = ng.nodes.new('NodeGroupOutput')
        self._x = 0

    # interface -------------------------------------------------------------
    def input(self, name, stype, default=None, lo=None, hi=None):
        s = self.ng.interface.new_socket(name, in_out='INPUT', socket_type=stype)
        if default is not None:
            s.default_value = default
        if lo is not None:
            s.min_value = lo
        if hi is not None:
            s.max_value = hi
        return s

    def output(self, name, stype='NodeSocketGeometry'):
        return self.ng.interface.new_socket(name, in_out='OUTPUT', socket_type=stype)

    def gi(self, name):
        return self.n_in.outputs[name]

    def set_output(self, name, sock):
        self.link(sock, self.n_out.inputs[name])

    # nodes -----------------------------------------------------------------
    def node(self, ntype, inputs=None, **props):
        n = self.ng.nodes.new(ntype)
        self._x += 40
        n.location = (self._x, 0)
        for k, v in props.items():
            setattr(n, k, v)
        for k, v in (inputs or {}).items():
            self.feed(sock(n.inputs, k), v)
        return n

    @classmethod
    def wrap(cls, node_tree):
        """Use the helpers on an existing tree (a material or world)."""
        t = cls.__new__(cls)
        t.ng, t._x = node_tree, 0
        return t

    def link(self, a, b):
        self.ng.links.new(a, b)

    def feed(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.link(v, sock)
        else:
            sock.default_value = v

    # math --------------------------------------------------------------------
    def m(self, op, a, b=None, c=None):
        n = self.node('ShaderNodeMath', operation=op)
        for i, v in enumerate((a, b, c)):
            if v is not None:
                self.feed(n.inputs[i], v)
        return n.outputs[0]

    def im(self, op, a, b=None):
        n = self.node('FunctionNodeIntegerMath', operation=op)
        for i, v in enumerate((a, b)):
            if v is not None:
                self.feed(n.inputs[i], v)
        return n.outputs[0]

    def v(self, op, a, b=None, scale=None):
        n = self.node('ShaderNodeVectorMath', operation=op)
        self.feed(n.inputs[0], a)
        if b is not None:
            self.feed(n.inputs[1], b)
        if scale is not None:
            self.feed(n.inputs['Scale'], scale)
        out = 'Value' if op in ('LENGTH', 'DOT_PRODUCT', 'DISTANCE') else 'Vector'
        return n.outputs[out]

    def xyz(self, x=0.0, y=0.0, z=0.0):
        n = self.node('ShaderNodeCombineXYZ')
        for i, val in enumerate((x, y, z)):
            self.feed(n.inputs[i], val)
        return n.outputs[0]

    def sep(self, vec):
        n = self.node('ShaderNodeSeparateXYZ')
        self.feed(n.inputs[0], vec)
        return n.outputs

    def join(self, *geos):
        n = self.node('GeometryNodeJoinGeometry')
        for g in geos:
            self.link(g, n.inputs[0])
        return n.outputs[0]

    def instances(self, geos):
        """Geometry to Instance whose instance index i is geos[i].

        The node's multi-input numbers its inputs in reverse link order
        (checked in 5.2), so link the list backwards.
        """
        n = self.node('GeometryNodeGeometryToInstance')
        for g in reversed(geos):
            self.link(g, n.inputs[0])
        return n.outputs[0]

    def set_menu(self, node, socket, value):
        node.inputs[socket].default_value = value


def reset_modifier_inputs(mod):
    """Copy the group's default input values into a nodes modifier.

    Rebuilding a group's interface gives its sockets new identifiers, which
    leaves the modifier's values at zero. Blender 5.2 stores them under
    mod.properties.inputs.<identifier>.value.
    """
    ins = mod.properties.inputs
    for item in mod.node_group.interface.items_tree:
        if item.item_type != 'SOCKET' or item.in_out != 'INPUT':
            continue
        if item.socket_type == 'NodeSocketGeometry' or not hasattr(item, 'default_value'):
            continue
        sock = getattr(ins, item.identifier, None)
        if sock is not None:
            sock.value = item.default_value
    mod.id_data.update_tag()   # writing inputs does not trigger re-evaluation
