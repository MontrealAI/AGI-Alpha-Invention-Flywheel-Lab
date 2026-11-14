"""Closed sampled preview mesh. Analytic SCAD + layout remain the design source.

This exports geometry only, not a mixed-material manufacturing recipe. Grid
resolution and physical qualification are deliberately separate quantities.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import struct
import numpy as np
from .build import audit, save
from .model import read, digest


def export_mesh(design_directory, mesh_directory, step_mm=.1):
    audit(design_directory)
    s=read(Path(design_directory)/'request.json')
    result=read(Path(design_directory)/'REPORT.json')
    if not result['independent_check']['accepted']:
        raise ValueError('mesh requires an accepted numerical design')
    g=read(Path(design_directory)/'layout.json')
    if type(step_mm) not in (int,float) or not math.isfinite(step_mm) or step_mm<=0:
        raise ValueError('positive finite preview resolution required')
    nx=math.ceil(g['width_mm']/step_mm);ny=math.ceil(g['depth_mm']/step_mm)
    if nx<2 or ny<2 or (nx+1)*(ny+1)>1_000_000:
        raise ValueError('preview grid outside declared resource envelope')
    out=Path(mesh_directory).absolute()
    if any(p.is_symlink() for p in (out,*out.parents)):
        raise ValueError('symlink output ancestry')
    out.mkdir(parents=True,exist_ok=False)
    xs=np.linspace(0,g['width_mm'],nx+1);ys=np.linspace(0,g['depth_mm'],ny+1)
    x,y=np.meshgrid(xs,ys,indexing='ij');z=np.full_like(x,s['base_thickness_mm'])
    families={f['id']:f for f in s['families']}
    for site in g['sites']:
        r=families[site['family']]['radius_mm'];h=site['height_mm']
        q=(x-site['x_mm'])**2+(y-site['y_mm'])**2
        bump=np.sqrt(np.maximum(0,r*r-q))-(r-h)
        z=np.maximum(z,s['base_thickness_mm']+np.maximum(bump,0))
    top=np.stack((x.ravel(),y.ravel(),z.ravel()),axis=1)
    bottom=top.copy();bottom[:,2]=0
    vertices=np.vstack((top,bottom));n=len(top)
    triangle_count=4*nx*ny+4*(nx+ny)
    with (out/'surface-preview.stl').open('xb') as f:
        f.write(b'GENESIS sampled geometry ONLY - not a material recipe or physical qualification'.ljust(80,b' '))
        f.write(struct.pack('<I',triangle_count))
        def triangle(a,b,c):
            pts=vertices[[a,b,c]]
            normal=np.cross(pts[1]-pts[0],pts[2]-pts[0]);norm=np.linalg.norm(normal)
            if norm<=0 or not np.isfinite(norm):raise ValueError('degenerate triangle')
            f.write(struct.pack('<12fH',*(normal/norm),*pts.ravel(),0))
        for i in range(nx):
            for j in range(ny):
                a=i*(ny+1)+j;b=a+ny+1;c=b+1;d=a+1
                triangle(a,b,c);triangle(a,c,d)
                triangle(a+n,c+n,b+n);triangle(a+n,d+n,c+n)
        boundary=([i*(ny+1) for i in range(nx+1)]
                  +[nx*(ny+1)+j for j in range(1,ny+1)]
                  +[i*(ny+1)+ny for i in range(nx-1,-1,-1)]
                  +[j for j in range(ny-1,0,-1)])
        for a,b in zip(boundary,boundary[1:]+boundary[:1]):
            triangle(a,b+n,b);triangle(a,a+n,b+n)
    p=out/'surface-preview.stl'
    if p.stat().st_size != 84+50*triangle_count:raise ValueError('STL count/length mismatch')
    receipt={'schema':'genesis/surface-preview/v1','design_sha256':digest(result['candidate']),
        'request_sha256':digest(s),'mesh_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
        'grid_step_mm':[g['width_mm']/nx,g['depth_mm']/ny],'triangles':triangle_count,
        'physical_qualified':False,'manufacturing_recipe':False,
        'scope':'Sampled closed height-field representation. Tessellation is approximate; separate topology checking and physical validation are required.'}
    save(out/'MESH.json',receipt)
    return receipt
