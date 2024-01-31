"""
Parse the psf/logFile (which is not a log file)
See https://github.com/KenKundert/psf_utils for some information on the PSF ASCII format.
"""
import itertools
import sys
from pathlib import Path
from typing import Any

from pyparsing import (Dict, Forward, Group, Literal, MatchFirst, OneOrMore, Opt, ParseResults, QuotedString, SkipTo,
                       Suppress, ZeroOrMore, pyparsing_common)


class PsfAsciiFile:
    pass


def read_asciipsf(path: Path) -> tuple[dict[str, Any], ParseResults]:
    text = path.read_text()
    qstring = QuotedString('"')
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

    custom_types = []

    def add_custom_type(tokens: ParseResults):
        """For each typedef, create a ParserExpression that will be used to parse the ValueSection entries."""
        name = tokens[1]
        if not isinstance(name, str):
            name = str(tokens[1].get_name())
        type_str = f'"{tokens[0]}"'
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
                expr = type_str + Suppress("(")
                a = Literal()
                for x in tokens[1][0]:
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
                expr += Group(a)
                expr += Suppress(")")
        custom_types.append(expr)

    typedef.set_parse_action(add_custom_type)
    type_section = Suppress("TYPE") + Dict(ZeroOrMore(Group(typedef)))  # type: ignore

    header_and_type = Group(header_section)("header") + Group(type_section)("type")
    result = header_and_type.parse_string(text)

    # print("\n== HEADER SECTION ==")
    # for name, value in result["header"].items():
    # print(f"{name}: {value}")

    header_dict = result["header"].as_dict()

    # print("\n== TYPE SECTION ==")
    # for name, item in result["type"].items():
    # print(name)
    #     if isinstance(item, ParseResults):
    #         print(f"{name}  -->  ")
    #         child = item.pop()
    #         if child.get_name() == '>struct':
    #             print("STRUCT:")
    #             for k, v in child.pop().items():
    #                 print(f"    {k}: {v}")
    #     else:
    #         print(f"{name}  -->  {item}")

    # print("\n== VALUE SECTION ==")
    # VALUE SECTION (needs the custom_types, so have to parse separately)
    typed_value = Group(MatchFirst(custom_types))
    props = Group(Dict(ZeroOrMore(property)))  # type: ignore
    property_list = Suppress("PROP") + Suppress("(") + props + Suppress(")")
    value_item = Group(qstring + typed_value + Opt(Suppress(property_list)))
    # value_item = Group(qstring + typed_value)

    value_section = Suppress(SkipTo("VALUE", include=True)) + Dict(ZeroOrMore(value_item))  # type: ignore
    result = value_section.parse_string(text)

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
            print(f"    {k} = {v}")


if __name__ == "__main__":
    # f = Path("psf_examples/psf_dcsweep_tran/logFile")
    # read_logfile_value_section(f)

    f = Path(sys.argv[1])
    header, result = read_asciipsf(f)

    print("HEADER:")
    for k, v in header.items():
        print(f"    {k:22}: {v}")

    print("\nVALUES:")

    for name, item in result.items():
        print(f"{name}:")
        for k, v in itertools.islice(item[1].as_dict().items(), 40):
            print(f"    {k:22}: {v}")
        # print("    ...")
