#  ----------------------------------------------------------------
# Copyright 2016 Cisco Systems
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------

""" py_types.py

    Contains python-cpp glue code for:
        - YList
        - YLeafList
        - Entity
"""
from ydk_ import is_set
from ydk.ext.types import Bits
from ydk.ext.types import ChildrenMap
from ydk.ext.types import Enum as _Enum
from ydk.ext.types import YLeaf as _YLeaf
from ydk.ext.types import YLeafList as _YLeafList
from ydk.ext.types import YType
from ydk.ext.types import Entity as _Entity
from ydk.ext.types import LeafDataList
from ydk.filters import YFilter as _YFilter
from ydk.errors import YPYModelError as _YPYModelError
from ydk.errors.error_handler import handle_type_error as _handle_type_error


class YList(list):
    """ Represents a list with support for hanging a parent

        All YANG based entity classes that have lists in them use YList
        to represent the list.

        The "list" statement is used to define an interior data node in the
        schema tree.  A list node may exist in multiple instances in the data
        tree.  Each such instance is known as a list entry.  The "list"
        statement takes one argument, which is an identifier, followed by a
        block of substatements that holds detailed list information.

        A list entry is uniquely identified by the values of the list's keys,
        if defined.
    """
    def __init__(self, parent):
        super(YList, self).__init__()
        self.parent = parent

    def __setattr__(self, name, value):
        if name == 'yfilter' and isinstance(value, _YFilter):
            for e in self:
                e.yfilter = value
        else:
            super(YList, self).__setattr__(name, value)

    def append(self, item):
        item.parent = self.parent
        super(YList, self).append(item)

    def extend(self, items):
       for item in items:
           self.append(item)


class YLeafList(_YLeafList):
    """ Wrapper class for YLeafList, add __repr__ and get list slice
    functionalities.
    """
    def __init__(self, ytype, leaf_name):
        super(YLeafList, self).__init__(ytype, leaf_name)
        self.ytype = ytype
        self.leaf_name = leaf_name

    def append(self, item):
        if isinstance(item, _YLeaf):
            item = item.get()
        super(YLeafList, self).append(item)

    def extend(self, items):
        for item in items:
            self.append(item)

    def set(self, other):
        if not isinstance(other, YLeafList):
            raise _YPYModelError("Invalid value '{}' in '{}'"
                            .format(other, self.leaf_name))
        else:
            super(YLeafList, self).clear()
            for item in other:
                self.append(item)

    def __getitem__(self, arg):
        if isinstance(arg, slice):
            indices = arg.indices(len(self))
            ret = YLeafList(self.ytype, self.leaf_name)
            values = [self.__getitem__(i).get() for i in range(*indices)]
            ret.extend(values)
            return ret
        else:
            arg = len(self) + arg if arg < 0 else arg
            return super(YLeafList, self).__getitem__(arg)

    def __str__(self):
        rep = [i for i in self.getYLeafs()]
        return "%s('%s', %r)" % (self.__class__.__name__, self.leaf_name, rep)


class Entity(_Entity):
    """ Entity wrapper class overrides some of the ydk::Entity methods.
    """
    def __init__(self):
        super(Entity, self).__init__()
        self._local_refs = {}
        self._children_name_map = {}
        self._children_yang_names = set()
        self._child_container_classes = {}
        self._child_list_classes = {}
        self._leafs = {}
        self._segment_path = lambda : ''
        self._absolute_path = lambda : ''

    def __eq__(self, other):
        if not isinstance(other, Entity):
            return False
        return super(Entity, self).__eq__(other)

    def __ne__(self, other):
        if not isinstance(other, Entity):
            return True
        return super(Entity, self).__ne__(other)

    def get_children(self):
        children = ChildrenMap()

        for name in self.__dict__:
            value = self.__dict__[name]
            if isinstance(value, Entity) and name != '_top_entity':
                if name not in self._children_name_map:
                    continue
                children[name] = value
            elif isinstance(value, YList):
                count=0
                for v in value:
                    if isinstance(v, Entity):
                        if v.get_segment_path() not in children:
                            children[v.get_segment_path()] = v
                        else:
                            children['%s%s' % (v.get_segment_path(), count)] = v
                            count += 1
        # store local refs so that pybind11 does not free the object. See https://github.com/pybind/pybind11/issues/673
        self._local_refs["ydk::children"] = children
        return children

    def get_order_of_children(self):
        order = []
        for name in self.__dict__:
            value = self.__dict__[name]
            if isinstance(value, YList):
                for v in value:
                    if isinstance(v, Entity):
                        order.append(v.get_segment_path())
        return order

    def get_child_by_name(self, child_yang_name, segment_path):
        child = self._get_child_by_seg_name([child_yang_name, segment_path])
        if child is not None:
            return child

        found = False
        is_container = True
        if child_yang_name in self._child_container_classes:
            found = True
        elif child_yang_name in self._child_list_classes:
            found = True
            is_container = False
        if found:
            if is_container:
                attr, clazz = self._child_container_classes[child_yang_name]
            else:
                attr, clazz = self._child_list_classes[child_yang_name]
            child = clazz()
            child.parent = self
            if is_container:
                self._children_name_map[attr] = child_yang_name
                setattr(self, attr, child)
            else:
                local_reference_key = "ydk::seg::%s" % segment_path
                self._local_refs[local_reference_key] = child
                getattr(self, attr).append(child)

            return child

        return None

    def has_data(self):
        for name, leaf in self._leafs.items():
            value = self.__dict__[name]
            if isinstance(value, _YFilter):
                return True
            if isinstance(leaf, _YLeaf):
                if value is not None:
                    if not isinstance(value, Bits) or len(value.get_bitmap()) > 0:
                        return True
            elif isinstance(leaf, _YLeafList) and len(value) > 0:
                return True
            elif isinstance(leaf, Entity) and leaf.has_data():
                return True
            elif isinstance(leaf, YList):
                for l in leaf:
                    if l.has_data():
                        return True
        return False

    def has_operation(self):
        if hasattr(self, 'yfilter') and is_set(self.yfilter):
            return True

        for name, value in vars(self).items():
            if value is not None:
                if name in self._leafs:
                    leaf = self._leafs[name]
                    isYLeaf = isinstance(leaf, _YLeaf)
                    isYLeafList = isinstance(leaf, _YLeafList)
                    isBits = isinstance(value, Bits)

                    if type(value) is _YFilter:
                        return True
                    if isYLeaf and (not isBits or len(value.get_bitmap()) > 0):
                        return True
                    if isYLeafList and len(value) > 0:
                        return True
                elif isinstance(value, Entity):
                    if is_set(value.yfilter) or value.has_operation():
                        return True
                elif isinstance(value, YList):
                    for v in value:
                        isEntity = isinstance(v, Entity)
                        if isEntity and (is_set(v.yfilter) or v.has_operation()):
                            return True
        return False

    def set_value(self, path, value, name_space='', name_space_prefix=''):
        for name, leaf in self._leafs.items():
            if leaf.name == path:
                if isinstance(leaf, _YLeaf):
                    if isinstance(self.__dict__[name], Bits):
                        self.__dict__[name][value] = True
                    else:
                        self.__dict__[name] = value
                elif isinstance(leaf, _YLeafList):
                    self.__dict__[name].append(value)

    def set_filter(self, path, yfilter):
        pass

    def has_leaf_or_child_of_name(self, name):
        for _, leaf in self._leafs.items():
            if name == leaf.name:
                return True

        if name in self._child_list_classes:
            return True

        if name in self._child_container_classes:
            return True

        return False

    def get_name_leaf_data(self):
        leaf_name_data = LeafDataList()
        for name in self._leafs:
            value = self.__dict__[name]
            leaf = self._leafs[name]

            if isinstance(value, _YFilter):
                leaf.yfilter = value
                if isinstance(leaf, _YLeaf):
                    leaf_name_data.append(leaf.get_name_leafdata())
                elif isinstance(leaf, _YLeafList):
                    leaf_name_data.extend(leaf.get_name_leafdata())
            elif (type(value) not in (list, type(None), Bits)
                or (isinstance(value, Bits) and len(value.get_bitmap()) > 0)):

                leaf.set(value)
                leaf_name_data.append(leaf.get_name_leafdata())
            elif isinstance(value, list) and len(value) > 0:
                l = _YLeafList(YType.str, leaf.name)
                # l = self._leafs[name]
                # Above results in YPYModelError:
                #     Duplicate leaf-list item detected:
                #     /ydktest-sanity:runner/ytypes/built-in-t/enum-llist[.='local'] :
                #     No resolvents found for leafref "../config/id"..
                #     Path: /ydktest-sanity:runner/one-list/identity-list/id-ref
                for item in value:
                    l.append(item)
                leaf_name_data.extend(l.get_name_leafdata())
        return leaf_name_data

    def get_segment_path(self):
        return self._segment_path()

    def get_absolute_path(self):
        return self._absolute_path()

    def _get_child_by_seg_name(self, segs):
        for seg in segs:
            for name in self._children_name_map:
                if seg == self._children_name_map[name]:
                    return self.__dict__[name]
        return None

    def _check_monkey_patching_error(self, name, value):
        obj = self.__dict__.get(name)
        if obj is None or isinstance(obj, (_YLeaf, YLeafList, YList)):
            return
        if type(value) is _YFilter:
            return

        if not isinstance(value, obj.__class__):
            raise _YPYModelError("Invalid value '{!s}' in '{}'"
                                 .format(value, obj))

    def _perform_setattr(self, clazz, leaf_names, name, value):
        self._check_monkey_patching_error(name, value)
        with _handle_type_error():
            if name in self.__dict__ and isinstance(self.__dict__[name], YList):
                raise _YPYModelError("Attempt to assign value of '{}' to YList ldata. "
                                    "Please use list append or extend method."
                                    .format(value))
            if isinstance(value, _Enum.YLeaf):
                value = value.name
            if name in leaf_names and name in self.__dict__:
                # bits ..?
                self.__dict__[name] = value

                leaf = self._leafs[name]
                if not isinstance(value, _YFilter):
                    if isinstance(leaf, _YLeaf):
                        leaf.set(value)
                    elif isinstance(leaf, _YLeafList):
                        leaf.clear()
                        for item in value:
                            leaf.append(item)

            else:
                if hasattr(value, "parent") and name != "parent":
                    if hasattr(value, "is_presence_container") and value.is_presence_container:
                        value.parent = self
                    elif value.parent is None and value.yang_name in self._children_yang_names:
                        value.parent = self
                super(Entity, self).__setattr__(name, value)


def _name_matches_yang_name(name, yang_name):
    return name == yang_name or yang_name.endswith(':'+name)
