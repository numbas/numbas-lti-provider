import difflib
import re

escape_map = str.maketrans({
    '\n': r'\n',
    '\\': r'\\',
})

def escape(s):
    return s.translate(escape_map)

def unescape(s):
    return re.sub(r'\\[\\n]',lambda m: '\n' if m[0][1]=='n' else '\\',s)

def make_diff(a,b):
    d = difflib.SequenceMatcher(None,a,b)
    output= []
    for opcode, i1,i2,j1,j2 in d.get_opcodes():
        if opcode == 'equal':
            pass
        elif opcode == 'delete':
            output.append(f'd{i1:x},{i2:x}')
        elif opcode == 'insert':
            s = escape(d.b[j1:j2])
            output.append(f'i{i1:x},{s}')
        elif opcode == 'replace':
            s = escape(d.b[j1:j2])
            output.append(f'r{i1:x},{i2:x},{s}')
    return '\n'.join(output)

def apply_diff(d,a):
    ops = d.split('\n')
    o = 0
    for op in ops:
        if not op:
            continue
        if op[0]=='d':
            i1,i2 = [int(x,16) for x in op[1:].split(',')]
            a = a[:o+i1]+a[i2+o:]
            o -= (i2-i1)
        elif op[0]=='i':
            bits = op[1:].split(',')
            i = int(bits[0],16)
            s = unescape(','.join(bits[1:]))
            a = a[:i+o]+s+a[i+o:]
            o += len(s)
        elif op[0]=='r':
            bits = op[1:].split(',')
            i1 = int(bits[0],16)
            i2 = int(bits[1],16)
            s = unescape(','.join(bits[2:]))
            a = a[:i1+o]+s+a[i2+o:]
            o += len(s)-(i2-i1)
    return a
