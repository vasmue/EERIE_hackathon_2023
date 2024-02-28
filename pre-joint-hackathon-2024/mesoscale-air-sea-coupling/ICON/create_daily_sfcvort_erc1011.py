#!/usr/bin/env python
# coding: utf-8

# 
# Compute mesoscale eddy-induced Ekman pumping (tau curl and vorticity gradient) 
#
import sys
yr=sys.argv[1]
mth=sys.argv[2]
yyyy=int(yr)

import glob, os
from subprocess import call
import multiprocessing
from netCDF4 import Dataset
import netCDF4 as nc
import xarray as xr
import numpy as np
import datetime

sys.path.insert(0, r'/home/m/m300466/pyfuncs')
from extractICONdata import *
from edgevertexcell import *

sys.path.append('/work/mh0256/m300466/pyicon')
import pyicon as pyic


run='erc1011'
gname = 'r2b9_oce_r0004'
lev = 'L128'
rgrid_name = 'global_0.05'
path_data     = f'/work/bm1344/k203123/experiments/{run}/'
path_grid     = f'/work/mh0256/m300466/icongrids/grids/{gname}/'
path_ckdtree  = f'{path_grid}ckdtree/'
fpath_ckdtree = f'{path_grid}ckdtree/rectgrids/{gname}_res0.05_180W-180E_90S-90N.npz'
#fpath_fx      = f'{path_grid}{gname}_{lev}_fx.nc'
#fpath_tgrid=f'{path_grid}{gname}_tgrid.nc'
fpath_tgrid=f'/pool/data/ICON/grids/public/mpim/0016/icon_grid_0016_R02B09_O.nc'
print(fpath_tgrid)
#exit(1)

f = Dataset(fpath_tgrid, 'r')
clon = f.variables['clon'][:] * 180./np.pi
clat = f.variables['clat'][:] * 180./np.pi
f.close()

#Fakely use atm model type to substitute for 2D ocean only [runs much faster!!!]
IcDo = pyic.IconData(
    fname        = run+'_oce_2d_1d_mean_20020101T000000Z.nc',
    path_data    = path_data+'run_20020101T000000-20020131T235845/',
    path_grid    = path_grid,
    gname        = gname,
    lev          = lev,
    rgrid_name   = rgrid_name,
    #load_rectangular_grid = False,
    do_triangulation    = False,
    omit_last_file      = False,
    load_vertical_grid = False,
    #calc_coeff          = True,
    #calc_coeff_mappings = False,
    model_type = 'atm',
              )

fpath_ckdtree = IcDo.rgrid_fpath_dict[rgrid_name]
IcDo.fixed_vol_norm = pyic.calc_fixed_volume_norm(IcDo)
IcDo.edge2cell_coeff_cc = pyic.calc_edge2cell_coeff_cc(IcDo)
IcDo.edge2cell_coeff_cc_t = pyic.calc_edge2cell_coeff_cc_t(IcDo)

expid='erc1011'
#outdir='/work/mh0287/m300466/EERIE/'+expid+'/Ekman/'
outdir='/work/mh0287/m300466/EERIE/'+expid+'/'
#ds2d = xr.open_mfdataset(path_data+'run_200[2-8]*/'+expid+'_oce_2d_1d_mean_'+'*T000000Z.nc')
#ds2d = xr.open_mfdataset(path_data+'run_'+str(yyyy)+'*/'+expid+'_oce_2d_1d_mean_'+'*T000000Z.nc')
if float(mth)<10:
    mm='0'+str(int(mth))
else:
    mm=str(int(mth))
ds2d = xr.open_mfdataset(path_data+'run_'+str(yyyy)+mm+'*/'+expid+'_oce_2d_1d_mean_'+'*T000000Z.nc')
#ds3d = xr.open_mfdataset(path_data+'run_200[2-8]*/'+expid+'_oce_ml_1d_mean_'+'*T000000Z.nc')

#Need vorticity grid
dso = xr.open_dataset('/work/mh0287/m300083/experiments/dpp0066/dpp0066_oce_3dlev_P1D_20200909T000000Z.nc')

gridds=xr.open_dataset(fpath_tgrid)
#Coriolis
omega=7.2921159e-5 #radians/second
fCo=2*omega*np.sin(gridds.clat.values)
Colatlim=2 #Coriolis latitude limit
g0=9.81 #gravity 
rho0=1024 #density ref

import numpy.ma as ma
fillval=np.nan
dsmask=gridds['cell_sea_land_mask']
lsmask2=ma.masked_values(np.where(dsmask.values!=-2,fillval,1),fillval)
lsmask=ma.masked_values(np.where(dsmask.values>=0,fillval,1),fillval)

#For daily data:
fdatearrf=ds2d.time.dt.strftime("%Y%m%d.%f")
fdatearr=ds2d.time.dt.strftime("%Y%m%d")
#Need to shift by 12 hours to get the right date
newdatearrflist=[]
newdatearrlist=[]
for tt in range(len(ds2d.time.data)):
    # newdatelist.append(datetime.datetime.strptime(str(ds2d.time.data[tt])[:10], '%Y-%m-%d')-datetime.timedelta(hours=12))
    newdatearrflist.append((datetime.datetime.strptime(str(ds2d.time.data[tt])[:10], '%Y-%m-%d')-datetime.timedelta(hours=12)).strftime("%Y%m%d.%f"))
    newdatearrlist.append((datetime.datetime.strptime(str(ds2d.time.data[tt])[:10], '%Y-%m-%d')-datetime.timedelta(hours=12)).strftime("%Y%m%d"))
newdatearrf=np.array(newdatearrflist)
newdatearr=np.array(newdatearrlist)

#for ii in range(0,1):
#for ii in range(0,np.shape(fdatearr)[0]):
for ii in range(0,len(fdatearr)):
    #fdate=str(fdatearr[ii].values)
    fdate=newdatearr[ii]
    print('Processing for '+fdate)

    print('Extracting surface zonal current')
    usfc=ds2d['u'].sel(time=fdatearr[ii]).values.squeeze()
    #print('size of u=',np.shape(usfc))
    print('Extracting surface meridional current')
    vsfc=ds2d['v'].sel(time=fdatearr[ii]).values.squeeze()
    #print('size of v=',np.shape(vsfc))

    # Wind stress curl
    print('Project fluxes on 3D sphere')
    p_sfc = pyic.calc_3d_from_2dlocal(IcDo, usfc[np.newaxis,:], vsfc[np.newaxis,:])
    print('p_tau=',np.shape(p_sfc))
    del(usfc)
    del(vsfc)

    # calculate edge array
    print('Project from cell centre to edges')
    ptp_sfc = pyic.cell2edges(IcDo, p_sfc.squeeze())
    print('ptp_sfc=',np.shape(ptp_sfc))
    del(p_sfc)
    
    print('rot_coeff=',np.shape(IcDo.rot_coeff))
    print('edges_of_vertex=',np.shape(IcDo.edges_of_vertex))
    print('Compute relative vorticity of surface current (single level)')
    ptv_relvort = (ptp_sfc[np.newaxis,IcDo.edges_of_vertex]*IcDo.rot_coeff[np.newaxis,:,:]).sum(axis=2)
    print('curl_tau=',np.shape(ptv_relvort))
    del(ptp_sfc)
    print('Convert to xarray')
    ptv_relvort=xr.DataArray(ptv_relvort.squeeze(), coords=dict(ncells_3=(["ncells_3"],dso.ncells_2.data)) , dims=["ncells_3"])
    print('Project from vertices to cell centre')
    relvort=vertex2cell(ptv_relvort,IcDo)
    del(ptv_relvort)
    print('relvort=',np.shape(relvort))
    #Denoise
    nrelvort=np.where(np.abs(relvort)>=4e-5,fillval,relvort)*lsmask2
    del(relvort)
    sfcvort=nrelvort/(rho0*fCo)*(rho0*fCo)
    print('Sfc vorticity=',np.shape(sfcvort))
    del(nrelvort)

    nctime = float(newdatearrf[ii])

    sfcvortfile=outdir+'sfcvort/dm/'+expid+'_sfcvort_dm_'+fdate+'.nc'
    print('Write to '+sfcvortfile)
    writenc1d_r2b9O(sfcvortfile,nctime,14886338,sfcvort,'sfcvort','Surface current relative vorticity','sfc_vort','1/s')

    del(sfcvort)
    