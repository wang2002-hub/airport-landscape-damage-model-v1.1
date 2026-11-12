from pathlib import Path
import ctypes as C
import json
import numpy as np
import pyogrio
from scipy import ndimage

CLASSES=np.array([11,12,21,22,23,24,31,41,42,43,52,71,81,82,90,95],dtype='uint8')
GROUPS={'water':[11],'developed':[21,22,23,24],'forest':[41,42,43],'shrub':[52],'grassland':[71],'pasture':[81],'cropland':[82],'wetland':[90,95],'other':[12,31]}
LUT=np.zeros(256,dtype=bool); LUT[CLASSES]=True
P=C.c_void_p; I=C.c_int; D=C.c_double; S=C.c_char_p
import os
g=C.CDLL(os.environ['BIRDSTRIKE_GDAL_LIBRARY'])
def api(name,restype,args):
    f=getattr(g,name); f.restype=restype; f.argtypes=args; return f
api('GDALAllRegister',None,[])()
api('CPLSetConfigOption',None,[S,S])(b'GDAL_PAM_ENABLED',b'NO')
api('GDALSetCacheMax64',None,[C.c_longlong])(256*1024*1024)
op=api('GDALOpen',P,[S,I]); close=api('GDALClose',None,[P])
width=api('GDALGetRasterXSize',I,[P]); height=api('GDALGetRasterYSize',I,[P])
nbands=api('GDALGetRasterCount',I,[P]); getband=api('GDALGetRasterBand',P,[P,I])
getgt=api('GDALGetGeoTransform',I,[P,C.POINTER(D)]); getproj=api('GDALGetProjectionRef',S,[P])
getnd=api('GDALGetRasterNoDataValue',D,[P,C.POINTER(I)]); getdt=api('GDALGetRasterDataType',I,[P])
rio=api('GDALRasterIO',I,[P,I,I,I,I,I,P,I,I,I,I,I])
driver=api('GDALGetDriverByName',P,[S]); create=api('GDALCreate',P,[P,S,I,I,I,I,C.POINTER(S)])
setgt=api('GDALSetGeoTransform',I,[P,C.POINTER(D)]); setproj=api('GDALSetProjection',I,[P,S])
setnd=api('GDALSetRasterNoDataValue',I,[P,D])
ogrcreate=api('OGR_G_CreateFromWkb',I,[P,P,C.POINTER(P),I]); ogrdestroy=api('OGR_G_DestroyGeometry',None,[P])
rasterize=api('GDALRasterizeGeometries',I,[P,I,C.POINTER(I),I,C.POINTER(P),P,P,C.POINTER(D),C.POINTER(S),P,P])
DTYPES={1:np.uint8,2:np.uint16,3:np.int16,4:np.uint32,5:np.int32,6:np.float32,7:np.float64}

class Raster:
    def __init__(self,path):
        self.path=Path(path); self.ds=op(str(self.path.resolve()).encode('utf-8'),0)
        if not self.ds: raise RuntimeError(f'Cannot open {path}')
        self.band=getband(self.ds,1); self.w=width(self.ds);self.h=height(self.ds)
        t=(D*6)(); assert getgt(self.ds,t)==0; self.gt=list(t)
        self.wkt=getproj(self.ds).decode(); self.dtype_code=getdt(self.band); self.dtype=DTYPES[self.dtype_code]
        flag=I(); v=getnd(self.band,C.byref(flag)); self.nodata=v if flag.value else None
        self.bands=nbands(self.ds)
        assert self.gt[2]==0 and self.gt[4]==0 and self.gt[1]>0 and self.gt[5]<0
    def read(self,col,row,nx,ny):
        assert 0<=col and 0<=row and col+nx<=self.w and row+ny<=self.h
        a=np.empty((ny,nx),dtype=self.dtype)
        err=rio(self.band,0,int(col),int(row),int(nx),int(ny),a.ctypes.data,int(nx),int(ny),self.dtype_code,0,0)
        if err: raise RuntimeError(f'Raster read error {err}: {self.path}')
        return a
    def window(self,bounds,pad=2):
        x0,y0,x1,y1=bounds;t=self.gt
        c0=max(0,int(np.floor((x0-t[0])/t[1]))-pad); c1=min(self.w,int(np.ceil((x1-t[0])/t[1]))+pad)
        r0=max(0,int(np.floor((y1-t[3])/t[5]))-pad); r1=min(self.h,int(np.ceil((y0-t[3])/t[5]))+pad)
        if c1<=c0 or r1<=r0: raise ValueError('No raster overlap')
        return c0,r0,c1-c0,r1-r0
    def window_gt(self,win):
        c,r,_,_=win;t=self.gt; return [t[0]+c*t[1],t[1],0,t[3]+r*t[5],0,t[5]]
    def release(self):
        if self.ds:close(self.ds); self.ds=None

def mask_polygon(poly,gt,shape,all_touched=False):
    ny,nx=shape;ds=create(driver(b'MEM'),b'',nx,ny,1,1,None)
    setgt(ds,(D*6)(*gt)); data=C.create_string_buffer(poly.wkb); geom=P()
    assert ogrcreate(data,None,C.byref(geom),len(poly.wkb))==0
    try:
        opts=(S*2)(b'ALL_TOUCHED=TRUE',None) if all_touched else None
        err=rasterize(ds,1,(I*1)(1),1,(P*1)(geom.value),None,None,(D*1)(1),opts,None,None)
        assert err==0
        a=np.empty((ny,nx),dtype=np.uint8)
        assert rio(getband(ds,1),0,0,0,nx,ny,a.ctypes.data,nx,ny,1,0,0)==0
        return a.astype(bool)
    finally:ogrdestroy(geom);close(ds)

def write_tif(path,a,gt,wkt,nodata=250):
    opts=(S*4)(b'COMPRESS=LZW',b'TILED=YES',b'BIGTIFF=IF_SAFER',None)
    dtype=next(k for k,v in DTYPES.items() if np.dtype(v)==a.dtype)
    ds=create(driver(b'GTiff'),str(path).encode('utf-8'),a.shape[1],a.shape[0],1,dtype,opts)
    assert ds
    try:
        setgt(ds,(D*6)(*gt));setproj(ds,wkt.encode());setnd(getband(ds,1),nodata)
        a=np.ascontiguousarray(a)
        assert rio(getband(ds,1),1,0,0,a.shape[1],a.shape[0],a.ctypes.data,a.shape[1],a.shape[0],dtype,0,0)==0
    finally:close(ds)

def structure(a,mask,res=30):
    valid=mask&LUT[a];n=int(valid.sum())
    if not n:return {'valid_n':0,'shdi':None,'edge_density_km_km2':None,'lpi_water_wetland_pct':None,'lpi_cropland_pct':None}
    cnt=np.bincount(a[valid],minlength=256)[CLASSES]; p=cnt[cnt>0]/n
    edges=int(((a[:,1:]!=a[:,:-1])&valid[:,1:]&valid[:,:-1]).sum()+((a[1:,:]!=a[:-1,:])&valid[1:,:]&valid[:-1,:]).sum())
    out={'valid_n':n,'shdi':float(-(p*np.log(p)).sum()),'edge_density_km_km2':edges*res/1000/(n*res**2/1e6)}
    for name,classes in [('water_wetland',[11,90,95]),('cropland',[82])]:
        labels,nlabels=ndimage.label(valid&np.isin(a,classes),structure=np.ones((3,3),dtype=np.uint8))
        biggest=int(np.bincount(labels.ravel())[1:].max()) if nlabels else 0
        out['lpi_'+name+'_pct']=100*biggest/n
        out['largest_'+name+'_pixels']=biggest
    return out

def dump(path,obj):
    Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
