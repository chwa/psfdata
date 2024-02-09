"""
Parse the psf/logFile (which is not a log file)
See https://github.com/KenKundert/psf_utils for some information on the PSF ASCII format.
"""
import sys
from itertools import islice
from pathlib import Path
from typing import Any

from pyparsing import (Dict, Forward, Group, Literal, MatchFirst, OneOrMore, Opt, ParseExpression, ParseResults,
                       QuotedString, SkipTo, Suppress, ZeroOrMore, pyparsing_common)

from pypsf.psf import PsfFile
from pypsf.waveform import Waveform


class PsfAsciiFile(PsfFile):
    def __init__(self, path: Path) -> None:
        super().__init__()
        self._header, self._result = read_asciipsf(path)

    @property
    def header(self) -> dict[str, Any]:
        return self._header

    @property
    def sweep_info(self) -> dict[str, Any] | None:
        ...

    @property
    def names(self) -> list[str]:
        ...

    def get_signal(self, name: str) -> Waveform:
        ...

    def get_signals(self, names: list[str]) -> dict[str, Waveform]:
        ...


qstring = QuotedString('"')


custom_types: list[ParseExpression] = []


def add_custom_type(typedef: ParseResults) -> None:
    """Add a ParserExpression to custom_types that can parse the type specified by typedef"""

    name = typedef[1]
    if not isinstance(name, str):
        name = str(typedef[1].get_name())
    type_str = f'"{typedef[0]}"'
    match name:
        case 'FLOAT' | 'DOUBLE':
            expr = type_str + pyparsing_common.fnumber
        case 'INT' | 'BYTE' | 'LONG':
            expr = type_str + pyparsing_common.signed_integer
        case '>string':
            expr = type_str + qstring
        case '>array':
            # TODO type of the array elements
            expr = type_str + Suppress("(") + Group(ZeroOrMore(pyparsing_common.number)) + Suppress(")")
        case '>struct':
            expr = Suppress(type_str) + Suppress("(")
            a = Literal()
            for x in typedef[1][0]:
                match x[1]:
                    case 'FLOAT' | 'DOUBLE':
                        subexpr = pyparsing_common.fnumber
                    case 'INT' | 'BYTE' | 'LONG':
                        subexpr = pyparsing_common.signed_integer
                    case 'STRING':
                        subexpr = qstring
                    case 'ARRAY':
                        # TODO type of the array elements
                        subexpr = Suppress("(") + ZeroOrMore(qstring) + Suppress(")")
                a += subexpr(x[0])  # attach the name of the struct member to the element
            expr += a  # Group(a)
            expr += Suppress(")")
    custom_types.append(expr)


def read_asciipsf(path: Path) -> tuple[dict[str, Any], ParseResults]:
    text = path.read_text()

    value = pyparsing_common.number | qstring

    # HEADER SECTION
    property = Group(qstring + value)
    header_section = Suppress("HEADER") + Dict(ZeroOrMore(property, stop_on="TYPE"))  # type: ignore

    # TYPE SECTION
    type_simple = (
        (Literal("FLOAT") + Literal("DOUBLE")) |  # spectre files use 'FLOAT DOUBLE'
        Literal("FLOAT") |
        Literal("DOUBLE") |
        Literal("COMPLEX") |
        Literal("INT") |
        Literal("BYTE") |
        Literal("LONG")
    )

    length = pyparsing_common.integer | Literal("*")  # not sure if a fixed length is allowed
    type_string = Literal("STRING") + length

    type_num_or_str = type_simple | type_string
    type_array = Literal("ARRAY") + Suppress("(") + length + Suppress(")") + type_num_or_str

    typedef_nested = Forward()
    struct_contents = Group(Dict(OneOrMore(Group(typedef_nested))))  # type: ignore
    # TODO: struct elements can also have props
    type_struct = Group(Suppress("STRUCT") + Suppress("(") + struct_contents + Suppress(")"))

    type_any = type_simple | type_string(">string") | type_struct(
        ">struct") | type_array(">array")

    props = Group(Dict(ZeroOrMore(property)))  # type: ignore
    property_list = Suppress("PROP") + Suppress("(") + props + Suppress(")")

    typedef_nested <<= (qstring + type_any + Opt(property_list))

    # non-nested (top level) typedef - only this will have the parse action attached
    typedef = typedef_nested.copy()

    typedef.set_parse_action(add_custom_type)
    type_section = Suppress("TYPE") + Dict(ZeroOrMore(Group(typedef)))  # type: ignore

    # SWEEP SECTION (optional)
    sweepdef = qstring("sweep_name") + qstring + Opt(property_list)
    sweep_section = Group(Suppress("SWEEP") + Dict(ZeroOrMore(Group(sweepdef))))("sweep_section")

    # TRACE SECTION (optional)
    tracedef = qstring("trace_name") + qstring("type_name")
    trace_section = Group(Suppress("TRACE") + Dict(ZeroOrMore(Group(tracedef))))("trace_section")

    sections = (Group(header_section)("header_section") +
                Group(type_section)("type_section") +
                Opt(sweep_section) +
                Opt(trace_section))
    result = sections.parse_string(text)
    header_dict = result["header_section"].as_dict()

    if "sweep_section" in result.keys():
        # swept value section:
        # <sweepvar> <value0>
        # <traceA> <value0>
        # <traceB> <value0>
        # <sweepvar> <value1>
        # <traceA> <value1>
        # <traceB> <value1>
        # ...
        custom_types_by_trace = []
        for k, v in result["trace_section"].items():
            print(k, v)
        pass
    else:
        typed_value = Group(MatchFirst(custom_types))
        value_item = Group(qstring + typed_value + Opt(Suppress(property_list)))
        # value_item = Group(qstring + value)
        value_section = Suppress(SkipTo("VALUE", include=True)) + Dict(ZeroOrMore(value_item)) + Suppress("END")
        values = value_section.parse_string(text)

        for name, val in values.items():
            print(f"{name}")
            for k, v in islice(val.items(), 5):
                print(f"    {k} = {str(v)[:50]}")
    # print("---------------")
    # print(values)
    # print("---------------")

    return header_dict, result


def read_logfile_value_section(path: Path):
    text = path.read_text()

    qstring = QuotedString('"')
    list_of_qstring = Suppress("(") + ZeroOrMore(qstring) + Suppress(")")
    value = pyparsing_common.number | qstring

    prop = Group(qstring + value)
    props = Group(Dict(ZeroOrMore(prop)))  # type: ignore
    property_list = Suppress("PROP") + Suppress("(") + props + Suppress(")")

    struct_contents = (qstring("analysis_type") +
                       qstring("data_file") +
                       qstring("format") +
                       qstring("parent") +
                       list_of_qstring("sweep_variable") +
                       qstring("description"))

    value_item = Group(qstring("name") + Suppress('"analysisInst"') +
                       Suppress("(") + struct_contents + Suppress(")") + Opt(property_list))

    value_section = Suppress(SkipTo("VALUE", include=True)) + \
        Dict(ZeroOrMore(value_item)) + Suppress("END")  # type: ignore
    result = value_section.parse_string(text, parse_all=True)

    for name, val in result.items():
        print(f"{name}")
        for k, v in val.items():
            print(f"    {k} = {str(v)[:50]}")


if __name__ == "__main__":
    # f = Path("psf_examples/psf_dcsweep_tran/logFile")
    # read_logfile_value_section(f)

    f = Path(sys.argv[1])
    header, result = read_asciipsf(f)
    exit()

    for s in ["header", "type", "sweep", "trace", "value"]:
        if f"{s}_section" in result:
            print(f"{s.upper()}:")
            result[f"{s}_section"].pprint()

    # print(custom_types)

    print("HEADER:")
    for k, v in header.items():
        print(f"    {k:22}: {v}")

    print("\nVALUES:")

    for name, item in result.items():
        print(f"{name}:")
        for k, v in itertools.islice(item[1].as_dict().items(), 40):
            print(f"    {k:22}: {v}")
        # print("    ...")
