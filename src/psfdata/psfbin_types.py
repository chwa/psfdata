from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

from .memview import MemoryViewAbs
from .psfbin_defs import TypeId

logger = logging.getLogger(__name__)


def read_properties(data: MemoryViewAbs) -> dict[str, str | int | float | tuple]:
    """Read zero or more simple properties and return them in a dict"""
    d = {}

    # The property block can be ended by any the following:
    # 0x10/0x11 means this is the next Type (or Group), not a property of the current Type
    # 0x12 is the struct end marker
    # not sure what 0x03 signifies...
    invalid = [0x03, 0x10, 0x11, 0x12]

    while len(data) and data.read_int32(peek=True) not in invalid:
        type = data.read_int32()

        # some properties don't have a name string ?
        if type == 0x24:  # used in the index file (tran.tran.tran) for PSFXL
            name = "psfxl_idx"
        else:
            name = data.read_string()

        value: str | int | float | tuple

        match type:
            case 0x01 | 0x04:
                continue
            case 0x21:
                value = data.read_string()
            case 0x22:
                value = data.read_int32()
            case 0x23:
                value = data.read_double()
            case 0x24:
                value = (
                    data.read_int64(),
                    data.read_int32(),
                    data.read_int32(),
                    data.read_double(),
                    data.read_double(),
                    data.read_double(),
                    data.read_double(),
                )
            case _:
                raise ValueError(f"Unknown Property type: {type=:#x}")
        d[name] = value

    return d


@dataclass
class TypeBase:
    id: int
    name: str
    properties: dict[str, str | int | float | tuple]


@dataclass
class TypeDef(TypeBase):
    typeid: TypeId
    struct_members: list[TypeDef] | None


@dataclass
class SignalDef(TypeBase):
    typedef: TypeDef

    @property
    def dtype(self) -> np.dtype:
        """Return the numpy dtype"""

        if self.typedef.typeid == TypeId.STRUCT:
            raise NotImplementedError("Trying to get dtype for struct")

        type = {
            TypeId.INT8: np.int8,  # not sure about this one
            TypeId.INT32: np.int32,
            TypeId.DOUBLE: np.float64,
            TypeId.COMPLEXDOUBLE: np.complex128
        }[self.typedef.typeid]

        return np.dtype(type)


@dataclass
class Group(TypeBase):
    children: list[SignalDef]


def read_id(data: MemoryViewAbs):
    kind = data.read_int32()
    assert kind in [0x10, 0x11]
    is_group = kind == 0x11

    id = data.read_int32()
    name = data.read_string()

    return id, name, is_group


def read_typedef(data: MemoryViewAbs) -> TypeDef:
    """Parse a datatype from the Type section"""
    id, name, is_group = read_id(data)
    assert not is_group

    ref = data.read_int32()
    assert ref == 0

    struct = None
    typeid = TypeId(data.read_int32())
    if typeid == TypeId.STRUCT:
        struct = []
        while data.read_int32(peek=True) != 0x12:
            c = read_typedef(data)
            struct.append(c)

        assert data.read_int32() == 0x12  # struct end marker
    properties = read_properties(data)

    return TypeDef(id, name, properties, typeid, struct)


def read_signaldef(data: MemoryViewAbs, typedefs: dict[int, TypeDef]) -> SignalDef | Group:
    """Parse an entry from the Trace or Sweep section"""
    id, name, is_group = read_id(data)

    if is_group:
        nchildren = data.read_int32()
        children = []
        for _ in range(nchildren):
            c = read_signaldef(data, typedefs)
            children.append(c)

        properties = read_properties(data)
        return Group(id, name, properties, children)
    else:
        reference = data.read_int32()
        assert reference != 0

        properties = read_properties(data)
        return SignalDef(id, name, properties, typedefs[reference])


def read_value(data: MemoryViewAbs, datatype: TypeDef):
    match datatype.typeid:
        case TypeId.INT8:
            return data.read_int32()  # TODO: =this is wrong
        case TypeId.INT32:
            return data.read_int32()
        case TypeId.DOUBLE:
            return data.read_double()
        case TypeId.COMPLEXDOUBLE:
            return data.read_cdouble()
        case TypeId.STRUCT:
            assert datatype.struct_members is not None
            return {c.name: read_value(data, c) for c in datatype.struct_members}
        case _:
            raise ValueError


def read_value_entry(data: MemoryViewAbs, typedefs: dict[int, TypeDef]):
    """Parse an entry from the (simple) Value section"""
    id, name, is_group = read_id(data)

    assert not is_group

    reference = data.read_int32()
    assert reference != 0

    # sdef = signaldefs[reference]
    # value = read_value(data, sdef.datatype)
    value = read_value(data, typedefs[reference])

    properties = read_properties(data)

    return id, name, value, properties


def get_complex_dtype(start_offset: int, sweep_def: SignalDef, traces: dict[int, SignalDef | Group]) -> np.dtype:
    """Returns the format/offset to be used in the np.dtype constructor (and the next start offset)"""

    offset = start_offset
    dtype_dict: dict[str, list] = {"names": [], "formats": [], "offsets": []}

    for item in [sweep_def] + list(traces.values()):

        offset += 8  # always skip the 2 int32s for 0x10 <id>

        if isinstance(item, Group):
            lst = item.children
        else:
            lst = [item]

        for signal in lst:
            if signal.typedef.typeid == TypeId.STRUCT:
                raise NotImplementedError("Trying to get dtype for struct in ValueSection.")

            format, size = {
                TypeId.INT8: (">i1", 1),  # not sure about this one
                TypeId.INT32: (">i4", 4),
                TypeId.DOUBLE: (">f8", 8),
                TypeId.COMPLEXDOUBLE: (">c16", 16)
            }[signal.typedef.typeid]

            dtype_dict["names"].append(signal.name)
            dtype_dict["formats"].append(format)
            dtype_dict["offsets"].append(offset)

            offset += size

    return np.dtype(dtype_dict)  # type: ignore
