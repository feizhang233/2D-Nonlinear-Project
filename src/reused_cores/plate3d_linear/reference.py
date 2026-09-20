"""Teaching reference only: planar Q4/MITC4 linear isotropic plate, SI units.
See A00-A05 for signs and limitations. Not a production or general shell solver.
"""
import numpy as np

CORNERS=np.array([[-1.,-1.],[1.,-1.],[1.,1.],[-1.,1.]])

def shape(xi,eta):
    a,b=CORNERS.T
    return (1+a*xi)*(1+b*eta)/4, np.column_stack((a*(1+b*eta)/4,b*(1+a*xi)/4))

def constitutive(E,nu,t,ks=5/6):
    if not np.isfinite([E,nu,t,ks]).all() or not (E>0 and -1<nu<.5 and t>0 and ks>0):
        raise ValueError('Invalid material or thickness')
    C=E/(1-nu**2)*np.array([[1,nu,0],[nu,1,0],[0,0,(1-nu)/2]])
    return C*t**3/12, np.eye(2)*ks*E/(2*(1+nu))*t

def raw(xy,xi,eta):
    N,dN=shape(xi,eta); J=xy.T@dN; det=np.linalg.det(J)
    scale=np.linalg.norm(J,ord=2)**2
    if not np.isfinite(det) or det<=1e-12*max(scale,np.finfo(float).tiny):
        raise ValueError('Nonpositive or near-degenerate Jacobian')
    grad=np.linalg.solve(J.T,dN.T).T
    Bb=np.zeros((3,12)); Bs=np.zeros((2,12))
    for i,(nx,ny) in enumerate(grad):
        j=3*i
        Bb[:,j:j+3]=[[0,nx,0],[0,0,ny],[0,ny,nx]]
        Bs[:,j:j+3]=[[nx,-N[i],0],[ny,0,-N[i]]]
    return N,J,det,Bb,Bs

def validate_xy(xy):
    xy=np.asarray(xy,float)
    if xy.shape!=(4,2) or not np.isfinite(xy).all(): raise ValueError('Expected finite (4,2) coordinates')
    for xi,eta in list(CORNERS)+[(0,-1),(0,1),(-1,0),(1,0),(0,0)]: raw(xy,xi,eta)
    return xy

def matrices(xy,xi,eta,method='mitc'):
    N,J,det,Bb,Bs=raw(xy,xi,eta)
    if method=='mitc':
        def cov(a,b,c):
            _,Jt,_,_,Bt=raw(xy,a,b)
            return Jt[:,c]@Bt
        bx=(1-eta)/2*cov(0,-1,0)+(1+eta)/2*cov(0,1,0)
        by=(1-xi)/2*cov(-1,0,1)+(1+xi)/2*cov(1,0,1)
        Bs=np.linalg.solve(J.T,np.vstack((bx,by)))
    elif method not in ('raw','sri'): raise ValueError('Unknown shear method')
    return N,J,det,Bb,Bs

def quadrature(order):
    pts,weights=np.polynomial.legendre.leggauss(order)
    return [(x,y,wx*wy) for x,wx in zip(pts,weights) for y,wy in zip(pts,weights)]

def element(xy,E=210e9,nu=.3,t=.1,ks=5/6,method='mitc',pressure=None):
    xy=validate_xy(xy); Db,Ds=constitutive(E,nu,t,ks)
    Kb=np.zeros((12,12)); Ks=Kb.copy(); f=np.zeros(12)
    for xi,eta,wt in quadrature(2):
        _,_,det,Bb,_=matrices(xy,xi,eta,method)
        Kb+=Bb.T@Db@Bb*det*wt
    for xi,eta,wt in quadrature(1 if method=='sri' else 2):
        _,_,det,_,Bs=matrices(xy,xi,eta,method)
        Ks+=Bs.T@Ds@Bs*det*wt
    if pressure is not None:
        for xi,eta,wt in quadrature(3):
            N,_,det,_,_=raw(xy,xi,eta); x,y=N@xy
            q=pressure(x,y) if callable(pressure) else pressure
            if not np.isfinite(q): raise ValueError('Invalid pressure')
            f[::3]+=N*q*det*wt
    return Kb+Ks,f,Kb,Ks

def space_basis(X):
    X=np.asarray(X,float)
    if X.shape!=(4,3) or not np.isfinite(X).all(): raise ValueError('Expected finite (4,3) coordinates')
    length=max(np.linalg.norm(x-y) for x in X for y in X)
    if length==0: raise ValueError('Zero extent')
    v=X[1]-X[0]; normal=np.cross(v,X[3]-X[0])
    if np.linalg.norm(v)<length*1e-12 or np.linalg.norm(normal)<length**2*1e-12:
        raise ValueError('Degenerate plane')
    ex=v/np.linalg.norm(v); n=normal/np.linalg.norm(normal); ey=np.cross(n,ex)
    Q=np.vstack((ex,ey,n)); local=(X-X[0])@Q.T
    if np.max(np.abs(local[:,2]))>length*1e-10: raise ValueError('Noncoplanar element')
    validate_xy(local[:,:2]); L=np.zeros((3,6))
    L[0,:3]=n; L[1,3:]=-ey; L[2,3:]=ex
    return Q,local[:,:2],np.kron(np.eye(4),L)

def solve_dirichlet(K,F,prescribed):
    fixed=np.array(sorted(prescribed),dtype=int); free=np.setdiff1d(np.arange(len(F)),fixed)
    d=np.zeros_like(F)
    if fixed.size: d[fixed]=[prescribed[i] for i in fixed]
    # Callers must provide sufficient physical boundary conditions; no diagonal regularization.
    if free.size: d[free]=np.linalg.solve(K[np.ix_(free,free)],F[free]-K[np.ix_(free,fixed)]@d[fixed])
    return d,K@d-F,free

def sine_reference(E,nu,t,a=1,q0=1,ks=5/6):
    Db,Ds=constitutive(E,nu,t,ks); D,S=Db[0,0],Ds[0,0]; p=np.pi/a
    Wb=q0/(4*D*p**4); Ws=q0/(2*S*p**2)
    return {'D':D,'S':S,'Wb':Wb,'Ws':Ws,'W':Wb+Ws,'rotation_amplitude':q0/(4*D*p**3),'shear_ratio':Ws/Wb}

def sine_mesh(n,t=.1,method='mitc',E=1,nu=.3,q0=1,a=1):
    if n<2 or n%2: raise ValueError('Use positive even n for a center node')
    nodes=np.array([(a*i/n,a*j/n) for j in range(n+1) for i in range(n+1)])
    nd=3*len(nodes); K=np.zeros((nd,nd)); F=np.zeros(nd)
    for j in range(n):
        for i in range(n):
            k=j*(n+1)+i; con=np.array([k,k+1,k+n+2,k+n+1])
            ids=(3*con[:,None]+np.arange(3)).ravel()
            ke,fe,_,_=element(nodes[con],E,nu,t,method=method,pressure=lambda x,y:q0*np.sin(np.pi*x/a)*np.sin(np.pi*y/a))
            K[np.ix_(ids,ids)]+=ke; F[ids]+=fe
    bc={}
    for j in range(n+1):
        for i in range(n+1):
            k=3*(j*(n+1)+i)
            if i in (0,n): bc.update({k:0.,k+2:0.})
            if j in (0,n): bc.update({k:0.,k+1:0.})
    d,R,free=solve_dirichlet(K,F,bc); center=3*((n//2)*(n+1)+n//2)
    ref=sine_reference(E,nu,t,a,q0)
    denom=max(np.linalg.norm(F),np.linalg.norm(K@d),1e-100)
    return {'n':n,'t_over_a':t/a,'method':method,'center_w':d[center],'exact_w':ref['W'],
            'ratio':d[center]/ref['W'],'relative_error':abs(d[center]/ref['W']-1),
            'free_residual':np.linalg.norm(R[free])/denom,
            'vertical_balance':abs(R[::3].sum()+F[::3].sum())/max(abs(F[::3].sum()),1e-100),
            'energy_error':abs(d@K@d-d@F)/max(abs(d@F),1e-100)}
