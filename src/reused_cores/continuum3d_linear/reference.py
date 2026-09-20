"""Small-strain isotropic Tet4/Hex8 teaching reference, not a production solver.
Voigt: xx, yy, zz, xy, yz, zx; engineering shear. Units must be consistent.
"""
import itertools
import numpy as np
SIGNS=np.array([[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]],float)
TET=np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,1]],float)
CUBE=(SIGNS+1)/2

def elastic(E,nu):
    if not np.isfinite([E,nu]).all() or E<=0 or not -1<nu<.5: raise ValueError('invalid isotropic material')
    mu=E/(2*(1+nu)); lam=E*nu/((1+nu)*(1-2*nu))
    D=np.zeros((6,6)); D[:3,:3]=lam; D[:3,:3]+=2*mu*np.eye(3); D[3:,3:]=mu*np.eye(3)
    return D

def shape(kind,q):
    q=np.asarray(q,float)
    if kind=='tet4': return np.r_[1-q.sum(),q],np.array([[-1,-1,-1],[1,0,0],[0,1,0],[0,0,1]],float)
    if kind!='hex8': raise ValueError('unsupported element')
    f=1+SIGNS*q; N=np.prod(f,axis=1)/8
    G=np.column_stack([SIGNS[:,j]*np.prod(f[:,[k for k in range(3) if k!=j]],axis=1)/8 for j in range(3)])
    return N,G

def gauss(kind,order=2):
    if kind=='tet4': return [(np.ones(3)/4,1/6)]
    x,w=np.polynomial.legendre.leggauss(order)
    return [(np.array([x[i],x[j],x[k]]),w[i]*w[j]*w[k]) for i,j,k in itertools.product(range(order),repeat=3)]

def bmatrix(G):
    B=np.zeros((6,3*len(G)))
    for i,(x,y,z) in enumerate(G): B[:,3*i:3*i+3]=[[x,0,0],[0,y,0],[0,0,z],[y,x,0],[0,z,y],[z,0,x]]
    return B

def point(kind,X,q):
    N,G=shape(kind,q); J=X.T@G
    scale=np.linalg.norm(J,2)
    if not np.isfinite(J).all() or scale<=0: raise ValueError('degenerate mapping')
    scaled=J/scale
    if np.linalg.det(scaled)<=1e-12 or np.linalg.cond(scaled)>1e10: raise ValueError('inverted or degenerate mapping')
    Gx=np.linalg.solve(J.T,G.T).T
    return N,bmatrix(Gx),float(np.linalg.det(J))

def element(kind,X,E=1000.,nu=.25,body=None,order=2):
    X=np.asarray(X,float); expected=4 if kind=='tet4' else 8
    if X.shape!=(expected,3) or not np.isfinite(X).all(): raise ValueError('invalid coordinates')
    D=elastic(E,nu)
    # These samples do NOT certify positive detJ throughout a warped hex.
    probes=[np.ones(3)/4] if kind=='tet4' else [*SIGNS,np.zeros(3)]
    for q in probes: point(kind,X,q)
    K=np.zeros((3*len(X),3*len(X))); F=np.zeros(3*len(X)); volume=0.
    for q,w in gauss(kind,order):
        N,B,j=point(kind,X,q); dv=w*j; K+=B.T@D@B*dv; volume+=dv
        if body is not None:
            b=np.asarray(body(N@X) if callable(body) else body,float)
            F+=(N[:,None]*b).ravel()*dv
    return K,F,volume

def face_load(X,traction):
    """Constant vector traction, NOT automatically oriented pressure."""
    X=np.asarray(X,float); t=np.asarray(traction,float)
    if len(X)==3:
        A=np.linalg.norm(np.cross(X[1]-X[0],X[2]-X[0]))/2
        return np.tile(t*A/3,(3,1))
    if len(X)!=4: raise ValueError('face must have 3 or 4 nodes')
    signs=np.array([[-1,-1],[1,-1],[1,1],[-1,1]],float); F=np.zeros((4,3))
    g,w=np.polynomial.legendre.leggauss(2)
    for i,j in itertools.product(range(2),repeat=2):
        r,s=g[i],g[j]; N=(1+signs[:,0]*r)*(1+signs[:,1]*s)/4
        G=np.column_stack([signs[:,0]*(1+signs[:,1]*s),signs[:,1]*(1+signs[:,0]*r)])/4
        J=X.T@G; da=np.linalg.norm(np.cross(J[:,0],J[:,1]))*w[i]*w[j]
        F+=N[:,None]*t*da
    return F

def structured(n):
    X=np.array(list(itertools.product(np.linspace(0,1,n+1),repeat=3)))
    def idx(i,j,k): return i*(n+1)**2+j*(n+1)+k
    cells=[]
    for i,j,k in itertools.product(range(n),repeat=3):
        cells.append([idx(i,j,k),idx(i+1,j,k),idx(i+1,j+1,k),idx(i,j+1,k),idx(i,j,k+1),idx(i+1,j,k+1),idx(i+1,j+1,k+1),idx(i,j+1,k+1)])
    return X,np.array(cells)

def dofs(cell): return (np.asarray(cell)[:,None]*3+np.arange(3)).ravel()

def assemble(X,cells,kind='hex8',E=1000.,nu=.25,body=None):
    K=np.zeros((3*len(X),3*len(X))); F=np.zeros(3*len(X))
    for cell in cells:
        if len(set(cell))!=len(cell) or min(cell)<0 or max(cell)>=len(X): raise ValueError('invalid connectivity')
        k,f,_=element(kind,X[cell],E,nu,body); ix=dofs(cell)
        K[np.ix_(ix,ix)]+=k;F[ix]+=f
    return K,F

def solve(K,F,prescribed):
    n=len(F); c=np.array(sorted(prescribed),dtype=int)
    if len(c) and (c[0]<0 or c[-1]>=n): raise ValueError('invalid constraint index')
    u=np.zeros(n);u[c]=[prescribed[i] for i in c]; f=np.setdiff1d(np.arange(n),c)
    if len(f):
        k=K[np.ix_(f,f)]; d=np.sqrt(np.maximum(np.diag(k),0))
        if np.any(d==0): raise ValueError('unrestrained or disconnected DOF')
        spectrum=np.linalg.eigvalsh(k/d[:,None]/d[None,:])
        if spectrum[0]<=1e-11*spectrum[-1]: raise ValueError('singular or ill-conditioned constrained stiffness')
        u[f]=np.linalg.solve(k,F[f]-K[np.ix_(f,c)]@u[c])
    return u,K@u-F

def stress_tensor(s):
    xx,yy,zz,xy,yz,zx=s;return np.array([[xx,xy,zx],[xy,yy,yz],[zx,yz,zz]])

def mises(s):
    xx,yy,zz,xy,yz,zx=s
    return np.sqrt(((xx-yy)**2+(yy-zz)**2+(zz-xx)**2)/2+3*(xy*xy+yz*yz+zx*zx))
