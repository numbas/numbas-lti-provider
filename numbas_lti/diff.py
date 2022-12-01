from diff_match_patch import diff_match_patch
import re

escape_map = str.maketrans({
    '\n': r'\n',
    '\\': r'\\',
})

def escape(s):
    return s.translate(escape_map)

def unescape(s):
    return re.sub(r'\\[\\n]',lambda m: '\n' if m[0][1]=='n' else '\\',s)

def make_diff(a, b):
    dmp = diff_match_patch()

    i = 0
    j = 0
    diffs = dmp.diff_main(a, b)
    output = []
    for n, (op, s) in enumerate(diffs):
        l = len(s)
        if op == diff_match_patch.DIFF_EQUAL:
            i += l
            j += l
        elif op == diff_match_patch.DIFF_DELETE:
            output.append(f'd{i:x},{i+l:x}')
            i += l
        elif op == diff_match_patch.DIFF_INSERT:
            es = escape(s)
            if n>0 and diffs[n-1][0] == diff_match_patch.DIFF_DELETE:
                output.pop()
                output.append(f'r{i-len(diffs[n-1][1]):x},{i:x},{es}')
            else:
                output.append(f'i{i:x},{es}')
            j += l
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
