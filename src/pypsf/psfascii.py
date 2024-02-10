"""
Parse the psf/logFile (which is not a log file)
See https://github.com/KenKundert/psf_utils for some information on the PSF ASCII format.
"""
import sys
from pathlib import Path
from typing import Any

from pyparsing import (Combine, Dict, Empty, Forward, Group, Literal, MatchFirst, OneOrMore, Opt, ParserElement,
                       ParseResults, QuotedString, SkipTo, Suppress, ZeroOrMore, pyparsing_common)

from .psf import PsfFile
from .waveform import Waveform

qstring = QuotedString('"')
def quoted(x): return Combine(Suppress(Literal('"')) + x + Suppress(Literal('"')))


value = pyparsing_common.number | qstring
named_prop = Group(qstring + value)
props = Group(Dict(ZeroOrMore(named_prop)))  # type: ignore
property_list = Suppress("PROP") + Suppress("(") + props + Suppress(")")


class PsfAsciiFile(PsfFile):
    def __init__(self, path: Path) -> None:
        super().__init__()

        self._custom_types: dict[str, ParserElement] = {}
        self._values: dict[str, Any] = {}
        self._text = path.read_text()

        self._read_info()
        if "sweep_section" in self._info.keys():
            self._read_sweep_values()
        else:
            self._read_simple_values()

    def _read_info(self) -> None:
        """Read header/type/trace/sweep sections"""
        # HEADER SECTION

        header_section = Suppress("HEADER") + Dict(ZeroOrMore(named_prop, stop_on="TYPE"))  # type: ignore

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

        typedef_nested <<= (qstring + type_any + Opt(property_list))

        # non-nested (top level) typedef - only this will have the parse action attached
        typedef = typedef_nested.copy()

        typedef.set_parse_action(self._add_custom_type)
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
        self._info = sections.parse_string(self._text)

        self._header = self._info["header_section"].as_dict()

    def _read_simple_values(self):
        # single value section:
        # <name> <type> <value>  where value is typically a struct
        typed_options = [quoted(k) + v for k, v in self._custom_types.items()]
        typed_value = Group(MatchFirst(typed_options))
        value_item = Group(qstring + typed_value + Opt(Suppress(property_list)))
        value_section = Suppress(SkipTo("VALUE", include=True)) + Dict(ZeroOrMore(value_item)) + Suppress("END")

        result = value_section.parse_string(self._text)
        for k, v in result.items():
            self._values[k] = v.as_dict()

    def _read_sweep_values(self):
        # swept value section:
        # <sweepvar> <value0>
        # <traceA> <value0>
        # <traceB> <value0>
        # <sweepvar> <value1>
        # <traceA> <value1>
        # <traceB> <value1>
        # ...

        sweep_var_type = self._info["sweep_section"][0]
        sweep_point = Group(quoted(sweep_var_type[0]) + self._custom_types[sweep_var_type[1]])

        for k, v in self._info["trace_section"].items():
            sweep_point += Group(quoted(k) + self._custom_types[v])

        value_section = Suppress(SkipTo("VALUE", include=True)) + \
            OneOrMore(Dict(sweep_point, asdict=True)) + Suppress("END")
        values = value_section.parse_string(self._text)

        self._values = {}
        for name in [sweep_var_type[0]] + list(self._info["trace_section"].keys()):
            self._values[name] = [d[name] for d in values]

    def _add_custom_type(self, typedef: ParseResults) -> None:
        """Add a ParserExpression to custom_types that can parse the type specified by typedef"""

        name = typedef[1]
        if not isinstance(name, str):
            name = str(typedef[1].get_name())
        type_str = typedef[0]  # f'"{typedef[0]}"'
        match name:
            case 'FLOAT' | 'DOUBLE':
                expr = pyparsing_common.fnumber
            case 'INT' | 'BYTE' | 'LONG':
                expr = pyparsing_common.signed_integer
            case '>string':
                expr = qstring
            case '>array':
                # TODO type of the array elements
                expr = Suppress("(") + Group(ZeroOrMore(pyparsing_common.number)) + Suppress(")")
            case '>struct':
                expr = Suppress("(")
                a = Empty()
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
                        case _:
                            raise Exception(f"Unknown type specifier: {x[1]}")
                    a += subexpr(x[0])  # attach the name of the struct member to the element
                expr += a
                expr += Suppress(")")
        self._custom_types[type_str] = expr

    @property
    def header(self) -> dict[str, Any]:
        return self._header

    @property
    def sweep_info(self) -> dict[str, Any] | None:
        ...

    @property
    def names(self) -> list[str]:
        return list(self._values.keys())

    def signal_info(self, name: str) -> dict[str, Any]:
        return {}

    def get_signal(self, name: str) -> Waveform:
        ...


if __name__ == "__main__":
    # f = Path("psf_examples/psf_dcsweep_tran/logFile")
    # read_logfile_value_section(f)

    fn = Path(sys.argv[1])

    with open(fn, 'rb') as f:
        print(bytes('HEADER', 'utf8'))
        print(f.read(6))

    exit()

    psf = PsfAsciiFile(fn)
    print()
    print(psf.header)
    print()
    for k, v in psf._values.items():
        print(f"==== {k} ====")
        print(str(v)[:100])
    # header, result = read_asciipsf(f)
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
