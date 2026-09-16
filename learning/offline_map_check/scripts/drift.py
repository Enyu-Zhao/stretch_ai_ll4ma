import numpy as np, glob, re
from scipy.spatial import cKDTree
def load(d):
    ids=sorted(int(re.findall(r"pose(\d+)",f)[0]) for f in glob.glob(d+"/pose*.npy"))
    return [(i,np.load(f"{d}/depth{i}.npy"),np.load(f"{d}/intrinsics{i}.npy"),np.load(f"{d}/pose{i}.npy")) for i in ids]
def cloud(fr,step=4):
    i,depth,K,P=fr; depth=depth[::step,::step]; H,W=depth.shape
    v,u=np.mgrid[0:H,0:W]; u=u*step; v=v*step
    m=(depth>0.25)&(depth<3.0)
    x=(u-K[0,2])*depth/K[0,0]; y=(v-K[1,2])*depth/K[1,1]
    c=np.stack([x[m],y[m],depth[m],np.ones(m.sum())],-1)
    return (c@P.T)[:,:3]
A=np.concatenate([cloud(f) for f in load("/work/data/lab_map_0")])
tree=cKDTree(A)
print("lab_map_1 frame -> lab_map_0 map residual (static structure only; moved objects/people inflate this)")
res=[]
for f in load("/work/data/lab_map_1"):
    w=cloud(f); d,_=tree.query(w,k=1); ov=d<0.3
    if ov.sum()>100:
        res.append(np.median(d[ov])); print(f"  frame {f[0]:2d}: median {np.median(d[ov])*100:5.1f} cm  overlap {ov.mean():.2f}")
print("overall median across frames: %.1f cm"%(np.median(res)*100))
