from enum import IntEnum


class SectionType(IntEnum):
    """These values are used to identify sections in the TOC."""
    HEADER = 0
    TYPE = 1
    SWEEP = 2
    TRACE = 3
    VALUE = 4


class TypeId(IntEnum):
    INT8 = 0x01
    INT32 = 0x05
    DOUBLE = 0x0B
    COMPLEXDOUBLE = 0x0C
    STRUCT = 0x10
