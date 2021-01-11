import string

def letter_ordinal(n):
    if n==0:
        return string.ascii_lowercase[0]
    s = ''
    while n>0:
        if s:
            n -= 1
        m = n%26
        s = string.ascii_lowercase[m]+s
        n = (n-m)//26
    return s

def hierarchy_key(x):
    key = x[0]
    try:
        return int(key)
    except ValueError:
        return key

def transform_part_hierarchy(hierarchy,transform,hierarchy_key=hierarchy_key):
    out = []

    def row(q,p=None,g=None,parent=None,has_gaps=False):
        qnum = int(q)+1
        path = 'q{}'.format(q)
        if p is not None:
            pletter = letter_ordinal(int(p))
            path += 'p{}'.format(p)
            if g is not None:
                path += 'g{}'.format(g)
        else:
            pletter = None

        info = {
            'q': q,
            'p': p,
            'g': g,
            'parent': parent,
            'has_gaps': has_gaps,
            'qnum': qnum,
            'path': path,
            'pletter': pletter,
        }
        return transform(**info)

    for i,q in sorted(hierarchy.items(),key=hierarchy_key):
        qnum = int(i)+1
        out.append(row(i))

        for j,p in sorted(q.items(),key=hierarchy_key):
            has_gaps = len(p['gaps'])>0
            prow = row(i, j, has_gaps=has_gaps)
            out.append(prow)

            for g in p['gaps']:
                out.append(row(i, j, g, prow))
    return out
