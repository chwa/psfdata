import logging
from typing import Any

import numpy as np

from pypsf.memview import MemoryViewAbs
from pypsf.psfbin_defs import TypeId

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
                    data.read_int32(),
                    data.read_int32(),
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


class DataType:
    """
    Used as:
      - datatype/unit definition in TypeSection
      - sweep variable in SweepSection
      - trace/signal definition in TraceSection
      - single-valued signal (can be struct) in SimpleValueSection
    """

    def __init__(self, data: MemoryViewAbs, typedefs: None | dict[int, Any] = None, with_value: bool = False):
        self.ref: DataType | None = None
        self.typeid: TypeId | None = None
        self.properties: dict = {}
        self.children: list[DataType] = []
        self.value = None

        if typedefs is None:
            typedefs = {}

        kind = data.read_int32()
        assert kind in [0x10, 0x11]
        self.is_group = kind == 0x11

        self.id = data.read_int32()
        self.name = data.read_string()

        if self.is_group:
            nchildren = data.read_int32()
            for _ in range(nchildren):
                c = DataType(data, typedefs=typedefs)
                self.children.append(c)
        else:
            if reference := data.read_int32():
                self.ref = typedefs[reference]
                if with_value:
                    self.value = self._read_data(data)
            else:
                self.typeid = TypeId(data.read_int32())
                if self.typeid == TypeId.STRUCT:
                    while data.read_int32(peek=True) != 0x12:
                        c = DataType(data, typedefs)
                        self.children.append(c)

                    assert data.read_int32() == 0x12  # struct end marker

        self.properties = read_properties(data)

    def __str__(self) -> str:
        s = f"Element {self.name!r} (0x{self.id:02x}):"
        if self.is_group:
            s += " Group:"
            for c in self.children:
                s += f"\n    - {c}"
        else:
            if self.ref is not None:
                s += f" [Reference to {self.ref.name!r} (0x{self.ref.id:02x})]"
            else:
                s += f" {self.number_type.name}"
            if self.value is not None:
                s += f" = {self.value}"
            if self.properties:
                s += f" {str(self.properties)[:44]}"
        return s

    def _read_data(self, data: MemoryViewAbs):
        dt = self
        while dt.ref is not None:
            dt = dt.ref

        match dt.typeid:
            case TypeId.INT8:
                return data.read_int32()  # TODO: =this is wrong
            case TypeId.INT32:
                return data.read_int32()
            case TypeId.DOUBLE:
                return data.read_double()
            case TypeId.COMPLEXDOUBLE:
                return data.read_cdouble()
            case TypeId.STRUCT:
                return {c.name: c._read_data(data) for c in dt.children}
            case _:
                raise ValueError(f"{dt.number_type}")

    @property
    def number_type(self) -> TypeId:
        if self.ref is not None:
            return self.ref.number_type
        assert self.typeid is not None
        return self.typeid

    @property
    def dtype(self) -> np.dtype:
        """Return the numpy dtype (for simple types)."""

        if self.number_type == TypeId.STRUCT:
            raise NotImplementedError("Trying to get dtype for struct in SweepSection/ValueSection.")

        type = {
            TypeId.INT8: np.int8,  # not sure about this one
            TypeId.INT32: np.int32,
            TypeId.DOUBLE: np.float64,
            TypeId.COMPLEXDOUBLE: np.complex128
        }[self.number_type]

        return np.dtype(type)

    def get_dtype_dict(self, offset: int) -> tuple[dict[str, Any], int]:
        """Return dict containing name/format/offset to be used in the np.dtype constructor."""

        if self.is_group:
            items = self.children
        else:
            items = [self]

        offset += 8  # always skip the 2 int32s for 0x10 <id>

        dtype_dict: dict[str, Any] = {
            "names": [],
            "formats": [],
            "offsets": [],
        }

        for item in items:
            if item.number_type == TypeId.STRUCT:
                raise NotImplementedError("Trying to get dtype for struct in SweepSection/ValueSection.")

            format, size = {
                TypeId.INT8: (">i1", 1),  # not sure about this one
                TypeId.INT32: (">i4", 4),
                TypeId.DOUBLE: (">f8", 8),
                TypeId.COMPLEXDOUBLE: (">c16", 16)
            }[item.number_type]

            dtype_dict["names"].append(item.name)
            dtype_dict["formats"].append(format)
            dtype_dict["offsets"].append(offset)

            offset = offset + size

        return dtype_dict, offset


def read_datatypes(data: MemoryViewAbs, typedefs: None | dict[int, DataType] = None, with_value: bool = False) -> dict[int, DataType]:
    """Read zero or more datatypes/groupdefs and return them in a dict."""
    d: dict[int, DataType] = {}
    while len(data):
        next = data.read_int32(peek=True)
        match next:
            case 0x03:
                return d  # TODO... does this mean anything?
            case 0x10 | 0x11:
                element = DataType(data, typedefs=typedefs, with_value=with_value)
            case _:
                raise ValueError(f"Unknown DataType starting with: {next=}")
        d[element.id] = element

    return d
