# AS6809

6809 one-pass assembler written in N88-BASIC(86), preserved as original implementation.

---

## Overview

AS6809 is a compact one-pass assembler for the Motorola 6809 CPU, written entirely in BASIC.

It allows machine code to be generated interactively by entering assembly instructions line by line.\
The assembled bytes are shown immediately together with the resulting address.

The source code preserved in this repository is a PC-9801 N88-BASIC(86) port of an earlier version originally written for the FM-new7.

![AS6809 Screenshot](images/as6809.png)

---

## Features

* One-pass interactive assembler
* Immediate machine code output
* Automatic address increment
* Supports common 6809 instructions
* Supports multiple addressing modes
* Compact implementation written entirely in BASIC
* Color text user interface

---

## Typical Usage

1. Start the program in N88-BASIC(86)
2. Enter a start address
3. Type assembly instructions line by line
4. Machine code is generated immediately
5. Continue assembling interactively

Example:

```asm
Address = $1000
1000 86 12        LDA #$12
1002 B6 12 34     LDA $1234
1005 96 34        LDA <$34
1007 20 F9        BRA $1002
```

---

## Background

This assembler was originally created during student years.

A friend had purchased an FM-new7 and wanted to learn assembly programming.\
Since an assembler was needed, a simple 6809 assembler was written overnight in BASIC.

Later, the program was ported to PC-9801 N88-BASIC(86).\
The source code preserved here is that later version.

---

## Implementation Notes

The program uses classic BASIC techniques such as:

* `DATA` statements for opcode tables
* String parsing for instruction decoding
* Addressing mode classification
* Relative branch offset calculation
* Compact table-driven logic

Although written in BASIC, the structure is optimized for practical use.

---

## Known Issues

The source code is preserved in its original historical form.

Some likely typographical mistakes are known:

* Line 160: possible typo in loop condition
* Line 45040: `DUBB` is likely intended to be `SUBB`

These are intentionally left unchanged for preservation purposes.

Interestingly, the assembler still operates correctly in normal use.

---

## Notes

* Intended for PC-9801 N88-BASIC(86) environment
* Originally derived from an FM-new7 version
* Preserved for historical and technical interest

---

## Status

This repository preserves the original implementation.

The source code is provided as-is,\
with minimal modification.

---

## License

MIT License
