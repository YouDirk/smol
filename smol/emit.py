
import sys

from .util import error, hash_djb2, eprintf
from .elf  import ELFMachine


def output_x86(libraries, nx, h16, outf):
    outf.write('; vim: set ft=nasm:\n') # be friendly

    #if nx:  outf.write('%define USE_NX 1\n')
    if nx:
        eprintf("NX not supported yet on i386.\n")
        nx = False
    if h16: outf.write('%define USE_HASH16 1\n')

    usedrelocs = set({})
    for library, symrels in libraries.items():
        for sym, reloc in symrels: usedrelocs.add(reloc)

    if not(nx) and 'R_386_PC32' in usedrelocs and 'R_386_GOT32X' in usedrelocs:
        error("Using a mix of R_386_PC32 and R_386_GOT32X relocations! "+\
              "Please change a few C compiler flags and recompile your code.")


    use_jmp_bytes = not nx and 'R_386_PC32' in usedrelocs
    if use_jmp_bytes:
        outf.write('%define USE_JMP_BYTES 1\n')

    outf.write('bits 32\n')

    shorts = { l: l.split('.', 1)[0].lower().replace('-', '_') for l in libraries }

    outf.write('%include "header-x86.asm"\n')
    outf.write('dynamic.needed:\n')
    for library in libraries:
        outf.write('dd 1;DT_NEEDED\n')
        outf.write('dd (_symbols.{} - _strtab)\n'.format(shorts[library]))
    outf.write("""\
dynamic.end:
%ifndef UNSAFE_DYNAMIC
    dd DT_NULL
%endif
""")

    outf.write('[section .rodata.neededlibs]\n')
    outf.write('_strtab:\n')
    for library, symrels in libraries.items():
        outf.write('\t_symbols.{}: db "{}",0\n'.format(shorts[library], library))

    outf.write('[section .data.smolgot]\n')
    if not nx:
        outf.write('[section .text.smolplt]\n')

    outf.write('_symbols:\n')
    for library, symrels in libraries.items():
        for sym, reloc in symrels:
            # meh
            if reloc != 'R_386_PC32' and reloc != 'R_386_GOT32X':
                error('Relocation type {} of symbol {} unsupported!'.format(reloc, sym))

            hash = hash_bsd2(sym) if h16 else hash_djb2(sym)
            if nx:
                outf.write("\t\t_symbols.{lib}.{name}: dd 0x{hash:x}\n"\
                    .format(lib=shorts[library],name=sym,hash=hash).lstrip('\n'))
            else:
                outf.write(("""\
\t\tglobal {name}
\t\t{name}:""" + ("\n\t\t\tdb 0xE9" if use_jmp_bytes else '') + """
\t\t\tdd 0x{hash:x}
""").format(name=sym, hash=hash).lstrip('\n'))

    outf.write('db 0\n')
    outf.write('_symbols.end:\n')

    if nx:
        outf.write('_smolplt:\n')
        for library, symrels in libraries.items():
            for sym, reloc in symrels:
                outf.write("""\
[section .text.smolplt.{name}]
global {name}
{name}:
\tjmp [dword _symbols.{lib}.{name}]
""".format(lib=shorts[library],name=sym).lstrip('\n'))

        outf.write('_smolplt.end:\n')

    outf.write('%include "loader-x86.asm"\n')


def output_amd64(libraries, nx, h16, outf):
    if h16:
        eprintf("--hash16 not supported yet for x86_64 outputs.")
        exit(1)

    if nx:  outf.write('%define USE_NX 1\n')
#   if h16: outf.write('%define USE_HASH16 1\n')

    outf.write('; vim: set ft=nasm:\n')
    outf.write('bits 64\n')

    shorts = { l: l.split('.', 1)[0].lower().replace('-', '_') for l in libraries }

    outf.write('%include "header-x86_64.asm"\n')
    outf.write('dynamic.needed:\n')
    for library in libraries:
        outf.write('    dq 1;DT_NEEDED\n')
        outf.write('    dq (_symbols.{} - _strtab)\n'.format(shorts[library]))
    outf.write("""\
dynamic.symtab:
    dq DT_SYMTAB        ; d_tag
    dq 0                ; d_un.d_ptr
dynamic.end:
%ifndef UNSAFE_DYNAMIC
    dq DT_NULL
%endif
""")

    outf.write('[section .rodata.neededlibs]\n')

    outf.write('_strtab:\n')
    for library, symrels in libraries.items():
        outf.write('\t_symbols.{}: db "{}",0\n'.format(shorts[library], library))

    outf.write('[section .data.smolgot]\n')

    outf.write('_symbols:\n')
    for library, symrels in libraries.items():
        for sym, reloc in symrels:
            if reloc not in ('R_X86_64_PLT32', 'R_X86_64_GOTPCRELX', 'R_X86_64_REX_GOTPCRELX'):
                error('Relocation type {} of symbol {} unsupported!'.format(reloc, sym))

            if reloc in ('R_X86_64_GOTPCRELX', 'R_X86_64_REX_GOTPCRELX'):
                outf.write("""
global {name}
{name}:
""".format(name=sym).lstrip('\n'))

            hash = hash_bsd2(sym) if h16 else hash_djb2(sym)
            outf.write('\t\t_symbols.{lib}.{name}: dq 0x{hash:x}\n'\
                       .format(lib=shorts[library],name=sym,hash=hash))

    outf.write('db 0\n')
    outf.write('_symbols.end:\n')

    outf.write('_smolplt:\n')
    for library, symrels in libraries.items():
        for sym, reloc in symrels:
            if reloc == 'R_X86_64_PLT32':
                outf.write("""\
[section .text.smolplt.{name}]
global {name}
{name}:
\tjmp [rel _symbols.{lib}.{name}]
""".format(lib=shorts[library],name=sym).lstrip('\n'))

    outf.write('_smolplt.end:\n')
    outf.write('%include "loader-x86_64.asm"\n')


def output_table(arch, libraries, nx, h16, outf):
    if   arch == ELFMachine.i386  : return output_x86(libraries, nx, h16, outf)
    elif arch == ELFMachine.x86_64: return output_amd64(libraries, nx, h16, outf)
    else:
        error('cannot emit for arch {}'.format(arch.name))

