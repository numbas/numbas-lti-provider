import string
import re
from datetime import timedelta
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

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

re_timeinterval = re.compile(r'P(?:(?P<years>\d+)Y)?(?:(?P<months>\d+)M)?(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?)?')

def parse_scorm_timeinterval(s):
    m = re_timeinterval.match(s)

    if not m:
        return 0

    lengths = {k: float(v) if v is not None else 0 for k,v in m.groupdict().items()}
    days = lengths['years']*365 + lengths['months']*30 + lengths['days']
    seconds = (lengths['hours']*60 + lengths['minutes'])*60 + lengths['seconds']

    return timedelta(days=days, seconds=seconds)

def add_query_param(url,extras):
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    for k,v in extras.items():
        if k not in query:
            query[k] = [v]
    url = urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params,
         urlencode(query,doseq=True), parsed.fragment)
    )
    return url
    
