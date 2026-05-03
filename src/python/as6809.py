#!/usr/bin/env python3
"""
as6809.py - experimental Python rewrite of AS6809

A small, interactive one-pass Motorola 6809 assembler inspired by
UG.'s original AS6809 written in N88-BASIC.

This version is intended as a readable modern companion implementation,
not yet a byte-for-byte replacement for the original BASIC program.

Design goals:
- Keep the spirit of the original interactive one-pass assembler.
- Preserve the table-driven instruction classification style.
- Generate machine code immediately after each input line.
- Keep the implementation compact and easy to study.

Supported features in this prototype:
- Many 6809 arithmetic / load / store instructions
- Immediate, direct, extended, indexed addressing
- Short and long branches
- Inherent instructions
- PSHS/PULS/PSHU/PULU register masks
- EXG/TFR register encoding

Limitations:
- No labels / symbol table
- No object file output
- Input expressions are simple numeric values only
- This is a study implementation, not a production assembler
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


class AsmError(Exception):
    pass


@dataclass(frozen=True)
class OpInfo:
    mnemonic: str
    base: int
    page: int = 0


@dataclass
class Encoded:
    page: int
    bytes_: list[int]

    def all_bytes(self) -> list[int]:
        if self.page:
            return [self.page] + self.bytes_
        return self.bytes_


# ----------------------------------------------------------------------
# Instruction tables
# ----------------------------------------------------------------------

# Group 1:
# 6809 instructions whose base opcode is combined with addressing-mode
# offsets. This follows the compact idea used in the BASIC version:
#   opcode = base + addressing_offset
# with optional page prefix.
GROUP1: dict[str, OpInfo] = {
    "SUBA": OpInfo("SUBA", 0x80),
    "CMPA": OpInfo("CMPA", 0x81),
    "SBCA": OpInfo("SBCA", 0x82),
    "SUBD": OpInfo("SUBD", 0x83),
    "CMPD": OpInfo("CMPD", 0x83, 0x10),
    "CMPU": OpInfo("CMPU", 0x83, 0x11),
    "ANDA": OpInfo("ANDA", 0x84),
    "BITA": OpInfo("BITA", 0x85),
    "LDA":  OpInfo("LDA",  0x86),
    "STA":  OpInfo("STA",  0x87),
    "EORA": OpInfo("EORA", 0x88),
    "ADCA": OpInfo("ADCA", 0x89),
    "ORA":  OpInfo("ORA",  0x8A),
    "ADDA": OpInfo("ADDA", 0x8B),
    "CMPX": OpInfo("CMPX", 0x8C),
    "CMPY": OpInfo("CMPY", 0x8C, 0x10),
    "CMPS": OpInfo("CMPS", 0x8C, 0x11),
    "JSR":  OpInfo("JSR",  0x8D),
    "LDX":  OpInfo("LDX",  0x8E),
    "LDY":  OpInfo("LDY",  0x8E, 0x10),
    "STX":  OpInfo("STX",  0x8F),
    "STY":  OpInfo("STY",  0x8F, 0x10),

    "SUBB": OpInfo("SUBB", 0xC0),
    "CMPB": OpInfo("CMPB", 0xC1),
    "SBCB": OpInfo("SBCB", 0xC2),
    "ADDD": OpInfo("ADDD", 0xC3),
    "ANDB": OpInfo("ANDB", 0xC4),
    "BITB": OpInfo("BITB", 0xC5),
    "LDB":  OpInfo("LDB",  0xC6),
    "STB":  OpInfo("STB",  0xC7),
    "EORB": OpInfo("EORB", 0xC8),
    "ADCB": OpInfo("ADCB", 0xC9),
    "ORB":  OpInfo("ORB",  0xCA),
    "ADDB": OpInfo("ADDB", 0xCB),
    "LDD":  OpInfo("LDD",  0xCC),
    "STD":  OpInfo("STD",  0xCD),
    "LDU":  OpInfo("LDU",  0xCE),
    "LDS":  OpInfo("LDS",  0xCE, 0x10),
    "STU":  OpInfo("STU",  0xCF),
    "STS":  OpInfo("STS",  0xCF, 0x10),
}

# Accumulator / memory operation group.
# These support direct / indexed / extended, plus A/B suffix forms.
GROUP2_BASE: dict[str, int] = {
    "NEG": 0x00,
    "COM": 0x03,
    "LSR": 0x04,
    "ROR": 0x06,
    "ASR": 0x07,
    "ASL": 0x08,
    "LSL": 0x08,
    "ROL": 0x09,
    "DEC": 0x0A,
    "INC": 0x0C,
    "TST": 0x0D,
    "JMP": 0x0E,
    "CLR": 0x0F,
}

SHORT_BRANCH_BASE: dict[str, int] = {
    "BRN": 0x21,
    "BHI": 0x22,
    "BLS": 0x23,
    "BCC": 0x24,
    "BHS": 0x24,
    "BCS": 0x25,
    "BLO": 0x25,
    "BNE": 0x26,
    "BEQ": 0x27,
    "BVC": 0x28,
    "BVS": 0x29,
    "BPL": 0x2A,
    "BMI": 0x2B,
    "BGE": 0x2C,
    "BLT": 0x2D,
    "BGT": 0x2E,
    "BLE": 0x2F,
    "BRA": 0x20,
    "BSR": 0x8D,
}

LONG_BRANCH_BASE: dict[str, tuple[int, int]] = {
    "LBRN": (0x10, 0x21),
    "LBHI": (0x10, 0x22),
    "LBLS": (0x10, 0x23),
    "LBCC": (0x10, 0x24),
    "LBHS": (0x10, 0x24),
    "LBCS": (0x10, 0x25),
    "LBLO": (0x10, 0x25),
    "LBNE": (0x10, 0x26),
    "LBEQ": (0x10, 0x27),
    "LBVC": (0x10, 0x28),
    "LBVS": (0x10, 0x29),
    "LBPL": (0x10, 0x2A),
    "LBMI": (0x10, 0x2B),
    "LBGE": (0x10, 0x2C),
    "LBLT": (0x10, 0x2D),
    "LBGT": (0x10, 0x2E),
    "LBLE": (0x10, 0x2F),
    "LBRA": (0x00, 0x16),
    "LBSR": (0x00, 0x17),
}

LEA_BASE: dict[str, int] = {
    "LEAX": 0x30,
    "LEAY": 0x31,
    "LEAS": 0x32,
    "LEAU": 0x33,
}

STACK_BASE: dict[str, int] = {
    "PSHS": 0x34,
    "PULS": 0x35,
    "PSHU": 0x36,
    "PULU": 0x37,
}

INHERENT: dict[str, tuple[int, int]] = {
    "NOP":  (0x00, 0x12),
    "SYNC": (0x00, 0x13),
    "DAA":  (0x00, 0x19),
    "SEX":  (0x00, 0x1D),
    "RTS":  (0x00, 0x39),
    "ABX":  (0x00, 0x3A),
    "RTI":  (0x00, 0x3B),
    "MUL":  (0x00, 0x3D),
    "SWI":  (0x00, 0x3F),
    "SWI2": (0x10, 0x3F),
    "SWI3": (0x11, 0x3F),
}

REGISTER_CODE: dict[str, int] = {
    "D":  0x0,
    "X":  0x1,
    "Y":  0x2,
    "U":  0x3,
    "S":  0x4,
    "PC": 0x5,
    "A":  0x8,
    "B":  0x9,
    "CC": 0xA,
    "DP": 0xB,
}

STACK_MASK: dict[str, int] = {
    "CC": 0x01,
    "A":  0x02,
    "B":  0x04,
    "DP": 0x08,
    "X":  0x10,
    "Y":  0x20,
    "U":  0x40,
    "S":  0x40,
    "PC": 0x80,
    "D":  0x06,
}

INDEX_REG: dict[str, int] = {
    "X": 0,
    "Y": 1,
    "U": 2,
    "S": 3,
}


# ----------------------------------------------------------------------
# Utility functions
# ----------------------------------------------------------------------

def clean_line(line: str) -> str:
    """Remove comments and normalize spacing."""
    # Keep this deliberately simple. AS6809.BAS itself is line-oriented
    # and does not implement labels or full expression syntax.
    line = line.strip()
    if not line:
        return ""
    # Accept ';' as a comment in this Python companion version.
    if ";" in line:
        line = line.split(";", 1)[0].strip()
    return line


def split_instruction(line: str) -> tuple[str, str]:
    line = clean_line(line)
    if not line:
        raise AsmError("empty line")
    parts = line.split(None, 1)
    mnemonic = parts[0].upper()
    operand = parts[1].replace(" ", "").upper() if len(parts) > 1 else ""
    return mnemonic, operand


def parse_number(text: str) -> int:
    """Parse simple numeric constants.

    Supported forms:
    - $1234
    - -$12
    - 1234
    - -12
    - 0x1234
    """
    if not text:
        raise AsmError("missing numeric value")

    sign = 1
    if text.startswith("-"):
        sign = -1
        text = text[1:]

    if text.startswith("$"):
        value = int(text[1:], 16)
    elif text.lower().startswith("0x"):
        value = int(text, 16)
    else:
        value = int(text, 10)

    value *= sign
    # Match the original BASIC program's signed adjustment behavior.
    if value > 32767:
        value -= 65536
    return value


def byte(value: int) -> int:
    return value & 0xFF


def word_bytes(value: int) -> list[int]:
    return [(value >> 8) & 0xFF, value & 0xFF]


def signed8(value: int) -> int:
    if not -128 <= value <= 127:
        raise AsmError(f"8-bit relative offset out of range: {value}")
    return value & 0xFF


def format_bytes(bytes_: list[int]) -> str:
    return " ".join(f"{b:02X}" for b in bytes_)


# ----------------------------------------------------------------------
# Addressing mode parser
# ----------------------------------------------------------------------

@dataclass
class Addressing:
    mode: str
    data: list[int]
    postbyte: Optional[int] = None


class Assembler:
    def __init__(self, origin: int = 0x1000):
        self.pc = origin

    def assemble_line(self, line: str) -> tuple[int, Encoded, str, str]:
        mnemonic, operand = split_instruction(line)
        address = self.pc
        encoded = self.encode(mnemonic, operand, address)
        self.pc += len(encoded.all_bytes())
        return address, encoded, mnemonic, operand

    def encode(self, mnemonic: str, operand: str, address: int) -> Encoded:
        if mnemonic in GROUP1:
            return self.encode_group1(GROUP1[mnemonic], operand)

        # Accumulator suffix form: ASLA, RORB, etc.
        for base_name, base in GROUP2_BASE.items():
            if mnemonic == base_name:
                return self.encode_group2(base_name, base, operand)
            if mnemonic == base_name + "A":
                if operand:
                    raise AsmError("unexpected operand")
                return Encoded(0, [base + 0x40])
            if mnemonic == base_name + "B":
                if operand:
                    raise AsmError("unexpected operand")
                return Encoded(0, [base + 0x50])

        if mnemonic in SHORT_BRANCH_BASE:
            return self.encode_short_branch(SHORT_BRANCH_BASE[mnemonic], operand, address)

        if mnemonic in LONG_BRANCH_BASE:
            page, op = LONG_BRANCH_BASE[mnemonic]
            return self.encode_long_branch(page, op, operand, address)

        if mnemonic in LEA_BASE:
            return self.encode_lea(LEA_BASE[mnemonic], operand)

        if mnemonic in STACK_BASE:
            return self.encode_stack(STACK_BASE[mnemonic], operand)

        if mnemonic in INHERENT:
            page, op = INHERENT[mnemonic]
            if operand:
                raise AsmError("unexpected operand")
            return Encoded(page, [op])

        if mnemonic == "ORCC":
            return self.encode_cc(0x1A, operand)
        if mnemonic == "ANDCC":
            return self.encode_cc(0x1C, operand)
        if mnemonic == "CWAI":
            return self.encode_cc(0x3C, operand)
        if mnemonic == "EXG":
            return self.encode_transfer(0x1E, operand)
        if mnemonic == "TFR":
            return self.encode_transfer(0x1F, operand)

        raise AsmError(f"unknown mnemonic: {mnemonic}")

    # ------------------------------------------------------------------
    # Encoder groups
    # ------------------------------------------------------------------

    def encode_group1(self, info: OpInfo, operand: str) -> Encoded:
        if not operand:
            raise AsmError("missing operand")

        mode = self.parse_addressing(operand)

        # Store instructions do not support immediate mode.
        if info.mnemonic.startswith("ST") and mode.mode == "imm":
            raise AsmError("store instruction cannot use immediate mode")

        # Immediate offset is +0x00, direct +0x10, indexed +0x20, extended +0x30.
        if mode.mode == "imm":
            op = info.base
            # 16-bit immediates for D/X/Y/U/S compare/load family.
            if info.mnemonic in {"SUBD", "CMPD", "CMPU", "CMPX", "CMPY", "CMPS", "LDX", "LDY", "LDU", "LDS", "LDD"}:
                data = mode.data[-2:]
            else:
                data = [mode.data[-1]]
            return Encoded(info.page, [op] + data)

        if mode.mode == "direct":
            return Encoded(info.page, [info.base + 0x10] + mode.data)
        if mode.mode == "indexed":
            return Encoded(info.page, [info.base + 0x20, mode.postbyte or 0] + mode.data)
        if mode.mode == "extended":
            return Encoded(info.page, [info.base + 0x30] + mode.data)

        raise AsmError(f"unsupported addressing mode: {mode.mode}")

    def encode_group2(self, name: str, base: int, operand: str) -> Encoded:
        if not operand:
            raise AsmError("missing operand")
        mode = self.parse_addressing(operand, allow_immediate=False)
        if mode.mode == "direct":
            return Encoded(0, [base] + mode.data)
        if mode.mode == "indexed":
            return Encoded(0, [base + 0x60, mode.postbyte or 0] + mode.data)
        if mode.mode == "extended":
            return Encoded(0, [base + 0x70] + mode.data)
        raise AsmError(f"unsupported addressing mode for {name}: {mode.mode}")

    def encode_short_branch(self, opcode: int, operand: str, address: int) -> Encoded:
        if not operand:
            raise AsmError("missing branch target")
        target = parse_number(operand)
        offset = target - address - 2
        return Encoded(0, [opcode, signed8(offset)])

    def encode_long_branch(self, page: int, opcode: int, operand: str, address: int) -> Encoded:
        if not operand:
            raise AsmError("missing branch target")
        target = parse_number(operand)
        length = 4 if page else 3
        offset = target - address - length
        return Encoded(page, [opcode] + word_bytes(offset))

    def encode_lea(self, opcode: int, operand: str) -> Encoded:
        mode = self.parse_indexed(operand, allow_indirect=False)
        return Encoded(0, [opcode, mode.postbyte or 0] + mode.data)

    def encode_stack(self, opcode: int, operand: str) -> Encoded:
        if not operand:
            raise AsmError("missing register list")
        mask = 0
        for reg in operand.split(","):
            reg = reg.strip().upper()
            if reg not in STACK_MASK:
                raise AsmError(f"unknown stack register: {reg}")
            mask |= STACK_MASK[reg]
        return Encoded(0, [opcode, mask])

    def encode_cc(self, opcode: int, operand: str) -> Encoded:
        mode = self.parse_addressing(operand)
        if mode.mode != "imm" or len(mode.data) != 1:
            raise AsmError("condition-code operation requires 8-bit immediate")
        return Encoded(0, [opcode, mode.data[0]])

    def encode_transfer(self, opcode: int, operand: str) -> Encoded:
        if "," not in operand:
            raise AsmError("EXG/TFR requires two registers")
        left, right = [part.strip().upper() for part in operand.split(",", 1)]
        if left not in REGISTER_CODE or right not in REGISTER_CODE:
            raise AsmError("unknown register in EXG/TFR")
        return Encoded(0, [opcode, (REGISTER_CODE[left] << 4) | REGISTER_CODE[right]])

    # ------------------------------------------------------------------
    # Addressing parsers
    # ------------------------------------------------------------------

    def parse_addressing(self, operand: str, allow_immediate: bool = True) -> Addressing:
        if not operand:
            raise AsmError("missing operand")

        if operand.startswith("#"):
            if not allow_immediate:
                raise AsmError("immediate mode not allowed")
            value = parse_number(operand[1:])
            if -128 <= value <= 255:
                return Addressing("imm", [byte(value)])
            return Addressing("imm", word_bytes(value))

        if operand.startswith("[") and operand.endswith("]"):
            inner = operand[1:-1]
            if "," in inner:
                mode = self.parse_indexed(inner, allow_indirect=True)
                mode.postbyte = (mode.postbyte or 0) | 0x10
                return mode
            value = parse_number(inner)
            return Addressing("indexed", word_bytes(value), 0x9F)

        if operand.startswith("<"):
            value = parse_number(operand[1:])
            return Addressing("direct", [byte(value)])

        if "," in operand:
            return self.parse_indexed(operand)

        value = parse_number(operand)
        # Match the original program's default: no '<' means extended.
        return Addressing("extended", word_bytes(value))

    def parse_indexed(self, operand: str, allow_indirect: bool = False) -> Addressing:
        if not operand:
            raise AsmError("missing indexed operand")

        # Forms: ,X  ,X+  ,X++  ,-X  ,--X
        if operand.startswith(","):
            tail = operand[1:]
            if tail.endswith("++"):
                reg = tail[:-2]
                return Addressing("indexed", [], self.reg_postbyte(reg, 0x81))
            if tail.endswith("+"):
                reg = tail[:-1]
                if allow_indirect:
                    raise AsmError("indirect auto increment by one is invalid")
                return Addressing("indexed", [], self.reg_postbyte(reg, 0x80))
            if tail.startswith("--"):
                reg = tail[2:]
                return Addressing("indexed", [], self.reg_postbyte(reg, 0x83))
            if tail.startswith("-"):
                reg = tail[1:]
                if allow_indirect:
                    raise AsmError("indirect auto decrement by one is invalid")
                return Addressing("indexed", [], self.reg_postbyte(reg, 0x82))
            return Addressing("indexed", [], self.reg_postbyte(tail, 0x84))

        left, right = operand.split(",", 1)
        left = left.strip()
        right = right.strip()

        # Accumulator offset forms: A,X / B,Y / D,U
        if left in {"A", "B", "D"}:
            base = {"A": 0x86, "B": 0x85, "D": 0x8B}[left]
            return Addressing("indexed", [], self.reg_postbyte(right, base))

        value = parse_number(left)

        if right == "PCR":
            # PC-relative indexed addressing. The size decision here mirrors
            # the rough intent of the original program, although a full
            # assembler would also know the current PC externally.
            # This prototype treats the operand as a literal displacement.
            if -128 <= value <= 127:
                return Addressing("indexed", [byte(value)], 0x8C)
            return Addressing("indexed", word_bytes(value), 0x8D)

        if right not in INDEX_REG:
            raise AsmError(f"unknown index register: {right}")

        reg = INDEX_REG[right]

        if -16 <= value <= 15 and not allow_indirect:
            return Addressing("indexed", [], (reg << 5) | (value & 0x1F))
        if -128 <= value <= 127:
            return Addressing("indexed", [byte(value)], 0x88 | (reg << 5))
        return Addressing("indexed", word_bytes(value), 0x89 | (reg << 5))

    @staticmethod
    def reg_postbyte(reg: str, base: int) -> int:
        reg = reg.strip().upper()
        if reg not in INDEX_REG:
            raise AsmError(f"unknown index register: {reg}")
        return base | (INDEX_REG[reg] << 5)


# ----------------------------------------------------------------------
# Interactive front-end
# ----------------------------------------------------------------------

def print_result(address: int, encoded: Encoded, mnemonic: str, operand: str) -> None:
    bytes_ = encoded.all_bytes()
    print(f"[1A[33m{address:04X}: [32m{format_bytes(bytes_):<15} {mnemonic:<7} {operand}")


def repl(origin: int) -> None:
    asm = Assembler(origin)

    while True:
        try:
            line = input(f"[33m{asm.pc:04X}:                [37m>[32m")
        except EOFError:
            print()
            break

        if not line.strip():
            break

        try:
            address, encoded, mnemonic, operand = asm.assemble_line(line)
        except (AsmError, ValueError) as exc:
            print(f"[31mError: {exc}")
            continue

        print_result(address, encoded, mnemonic, operand)


def main() -> None:
    print()
    print("[37mAS6809 Python version")
    print()

    try:
        text = input("[36mAddress = $").strip()
        origin = int(text, 16) if text else 0x1000
    except ValueError:
        print("Invalid address")
        return
    repl(origin)


if __name__ == "__main__":
    main()
