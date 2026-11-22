"""Authored exact finite-field codec and conventional code constructors."""
from itertools import combinations
import numpy as np

EXP = [0] * 512
LOG = [0] * 256
v = 1
for i in range(255):
    EXP[i], LOG[v] = v, i
    v <<= 1
    if v & 256:
        v ^= 0x11D
for i in range(255, 512):
    EXP[i] = EXP[i-255]

def mul(a, b):
    return 0 if a == 0 or b == 0 else EXP[LOG[a]+LOG[b]]

def inv(a):
    if a == 0:
        raise ValueError('zero inverse')
    return EXP[255-LOG[a]]

MUL = np.array([[mul(a,b) for b in range(256)] for a in range(256)], dtype=np.uint8)

def rref(rows):
    a = [list(map(int,r)) for r in rows]
    piv = []
    t = 0
    for j in range(8):
        p = next((i for i in range(t,len(a)) if a[i][j]), None)
        if p is None:
            continue
        a[t],a[p] = a[p],a[t]
        z = inv(a[t][j]); a[t] = [mul(z,x) for x in a[t]]
        for i in range(len(a)):
            if i != t and a[i][j]:
                z=a[i][j];a[i]=[x^mul(z,y) for x,y in zip(a[i],a[t])]
        piv.append(j);t+=1
        if t==len(a):
            break
    return a[:t],piv

def rank(rows):
    return len(rref(rows)[1])

def contained(row, basis, piv):
    v = list(map(int,row))
    for b,p in zip(basis,piv):
        z=v[p]
        if z:
            v=[x^mul(z,y) for x,y in zip(v,b)]
    return not any(v)

def inverse(a):
    n=len(a); a=[list(map(int,r))+[int(i==j) for j in range(n)] for i,r in enumerate(a)]
    for j in range(n):
        p=next((i for i in range(j,n) if a[i][j]),None)
        if p is None:
            raise ValueError('singular')
        a[j],a[p]=a[p],a[j];z=inv(a[j][j]);a[j]=[mul(z,x) for x in a[j]]
        for i in range(n):
            if i!=j:
                z=a[i][j]
                if z:a[i]=[x^mul(z,y) for x,y in zip(a[i],a[j])]
    return [r[n:] for r in a]

def apply(matrix, data):
    m=np.asarray(matrix,dtype=np.uint8)
    d=np.asarray(data,dtype=np.uint8)
    if m.ndim!=2 or d.ndim!=2 or m.shape[1]!=d.shape[0]:
        raise ValueError('dimensions')
    return np.bitwise_xor.reduce(MUL[m[:,:,None],d[None,:,:]],axis=1)

def systematic(parity):
    return [[int(i==j) for j in range(8)] for i in range(8)]+parity

def rs():
    return systematic([[inv(i^(8+j)) for i in range(8)] for j in range(6)])

def lrc():
    # Row-scaled Cauchy: first global is total XOR, available from both locals.
    glob=[[mul(i^8,inv(i^(8+j))) for i in range(8)] for j in range(4)]
    return systematic(glob+[[int(i<4) for i in range(8)],[int(i>=4) for i in range(8)]])

def binary(masks):
    return systematic([[(m>>i)&1 for i in range(8)] for m in masks])

def hamming_masks():
    positions=[3,5,6,7,9,10,11,12]
    p=[sum((1<<i) for i,x in enumerate(positions) if x&(1<<j)) for j in range(4)]
    z=255
    for x in p:z^=x
    return p+[z,255]

def failures(racks):
    return [tuple(s) for k in (1,2,3) for s in combinations(range(14),k)]+[tuple(r) for r in racks]

def decoder(g, lost):
    available=[i for i in range(14) if i not in lost]
    chosen=[];rr=0
    for i in available:
        q=rank([g[j] for j in chosen]+[g[i]])
        if q>rr:chosen.append(i);rr=q
        if rr==8:return chosen,inverse([g[j] for j in chosen])
    return None

def minimum_repairs(g):
    """Exhaustive helper-subset closure, not a heuristic repair claim."""
    result=[None]*14; witness=[None]*14
    for k in range(1,9):
        for subset in combinations(range(14),k):
            unresolved=[i for i in range(14) if result[i] is None and i not in subset]
            if not unresolved:continue
            basis,piv=rref([g[j] for j in subset])
            for i in unresolved:
                if contained(g[i],basis,piv):result[i]=k;witness[i]=list(subset)
        if all(x is not None for x in result):break
    return result,witness

def binary_eval(masks, racks):
    code=[0]*256
    for d in range(1,256):
        bit=d&-d;i=bit.bit_length()-1
        code[d]=code[d^bit]^bit^sum((((p>>i)&1)<<(8+j)) for j,p in enumerate(masks))
    bad=sum(c.bit_count()<4 for c in code[1:])
    rm=[sum(1<<i for i in r) for r in racks]
    bad+=sum(any(c&~r==0 for c in code[1:]) for r in rm)
    best=[15]*14
    relations=[p|(1<<(8+j)) for j,p in enumerate(masks)]
    dual=[0]*64
    for s in range(1,64):
        z=s&-s;d=dual[s^z]^relations[z.bit_length()-1];dual[s]=d;w=d.bit_count()-1
        for i in range(14):
            if (d>>i)&1 and w<best[i]:best[i]=w
    return bad*100000+max(best)*1000+sum(best),bad,best,min(c.bit_count() for c in code[1:])
