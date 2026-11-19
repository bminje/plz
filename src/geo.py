import numpy as np
# GRS80 Transverse Mercator inverse (EPSG:5186-like: lat0=38, lon0=127, k=1, FE=200000, FN=600000)
a=6378137.0; f=1/298.257222101; e2=2*f-f*f; ep2=e2/(1-e2)
def _M(phi,lat0=np.radians(38)):
    def m(p): return a*((1-e2/4-3*e2**2/64-5*e2**3/256)*p-(3*e2/8+3*e2**2/32+45*e2**3/1024)*np.sin(2*p)+(15*e2**2/256+45*e2**3/1024)*np.sin(4*p)-(35*e2**3/3072)*np.sin(6*p))
    return m(phi)-m(lat0)
def tm_to_wgs(x,y,lon0=127.0,lat0=38.0,k0=1.0,fe=200000.0,fn=600000.0):
    x=np.asarray(x,float); y=np.asarray(y,float)
    M=(y-fn)/k0+_M(np.radians(lat0),0) if False else None
    def m(p): return a*((1-e2/4-3*e2**2/64-5*e2**3/256)*p-(3*e2/8+3*e2**2/32+45*e2**3/1024)*np.sin(2*p)+(15*e2**2/256+45*e2**3/1024)*np.sin(4*p)-(35*e2**3/3072)*np.sin(6*p))
    M=m(np.radians(lat0))+(y-fn)/k0
    mu=M/(a*(1-e2/4-3*e2**2/64-5*e2**3/256))
    e1=(1-np.sqrt(1-e2))/(1+np.sqrt(1-e2))
    phi1=mu+(3*e1/2-27*e1**3/32)*np.sin(2*mu)+(21*e1**2/16-55*e1**4/32)*np.sin(4*mu)+(151*e1**3/96)*np.sin(6*mu)+(1097*e1**4/512)*np.sin(8*mu)
    C1=ep2*np.cos(phi1)**2; T1=np.tan(phi1)**2
    N1=a/np.sqrt(1-e2*np.sin(phi1)**2); R1=a*(1-e2)/(1-e2*np.sin(phi1)**2)**1.5
    D=(x-fe)/(N1*k0)
    lat=phi1-(N1*np.tan(phi1)/R1)*(D**2/2-(5+3*T1+10*C1-4*C1**2-9*ep2)*D**4/24+(61+90*T1+298*C1+45*T1**2-252*ep2-3*C1**2)*D**6/720)
    lon=np.radians(lon0)+(D-(1+2*T1+C1)*D**3/6+(5-2*C1+28*T1-3*C1**2+8*ep2+24*T1**2)*D**5/120)/np.cos(phi1)
    return np.degrees(lon),np.degrees(lat)
def hav(lat1,lon1,lat2,lon2):
    R=6371008.8
    p1,p2=np.radians(lat1),np.radians(lat2); dphi=p2-p1; dl=np.radians(lon2-lon1)
    h=np.sin(dphi/2)**2+np.cos(p1)*np.cos(p2)*np.sin(dl/2)**2
    return 2*R*np.arcsin(np.sqrt(h))
