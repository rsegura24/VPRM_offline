 #!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VPRM offline for EU sites to compare to FLUXNET observations.
Input: ECMWF met data: temperature, downward shortwave radiation
       or WRF met data: tempeature, downward shortwave radiation
       MODIS data     : EVI, LSWI, Land cover type.
       Flux obs.: flux measurement from FLUXNET2015
"""


from netCDF4 import Dataset
import numpy as np
import pandas as pd
from os import listdir
from calendar import monthrange
#from datetime import datetime, timedelta
from src.get_modis_point import get_modis_point
import src.WriteVPRMConstants as WriteVPRMConstants
from OfflineVPRM import julian
from scipy import interpolate

"""
0. Initialization
"""

year = 2015

input_origin = 'ERA5' #options are 'ERA5' or 'WRF' 
wrf_domain = 1 #Only needed in case input_origin = 'WRF'

filterTF = True #Using filtered MODIS data or not
modispre = [0,0] #prediction methods for MODIS: EVI, LSWI. (0 for no prediction, 1 for linear, 2 for persistence)
sim = 'perLSWI' #tag for simulation output

### Information of input and output
workpath = './' #Set your work path
outpath = workpath + 'VPRMoutput/' #Path to output file
stations_file = '/home/users/rsegura/Stations_data/Stations_info.csv'
StationDataPath = '/home/users/rsegura/Stations_data/'
if input_origin == 'ERA5':
    Metpath = workpath + 'data/ERA5/'
elif input_origin == 'WRF':
    Metpath = workpath + 'data/WRF_9km/'
MODISpath = workpath + 'data/MODIS/'
tag = 'test'
###Other settings
vprm_par_name = 'vprmopt.EU2007.local.par.csv'
parapath = workpath + 'data/VPRMparameters/'

#get parameters, reduce to 8 vegetation classes (no 4 evergreens needed, one enough)
VegClass = 8
vprmConstants = WriteVPRMConstants.WriteVPRMConstants(outdir = outpath, nveg = 8)
#### 8 vegetation classes: evergreen,deciduous,mixed forest,shrubland, savanna, cropland, grassland, others######


igbp_dict = {'ENF':0,'EBF':0, 'DNF':1, 'DBF':1, 'MF':2, 'CSH':3, 'OSH':3, 'WS':4, 'SAV':4, 'GRA':6, 'CRO':5, }

"""
1. READ INPUT TOWER DATA
"""
stations = pd.read_csv(stations_file, sep = ',')

snames = stations['Station']
vegfra_types = ['Evergreen','Decid', 'Mixfrst','Shrub','Savan','Crop','Grass','Other']
vprm_class = ["Evergreen Forest","Deciduous Forest","Mixed Forest","Shrubland","Savannas","Cropland","Grassland","Others"]

"""
vprm_opt = pd.read_csv(parapath+vprm_par_name, sep = ',')
    
for i, row in vprm_opt.iterrows():
    vprmConstants.loc[row['v.class']-1, 'parZero'] = row['PAR0']
    vprmConstants.loc[row['v.class']-1, 'lambdaGPP.sw'] = row['lambda']
    vprmConstants.loc[row['v.class']-1, 'alphaResp'] = row['alpha']
    vprmConstants.loc[row['v.class']-1, 'intResp'] = row['int']
"""

for station in stations['Station'].unique():
    fls = listdir(StationDataPath)
    fls = [x for x, y in zip(fls, [(station in file) for file in fls]) if y == True]
    fls = [x for x, y in zip(fls, [(str(year) in file) for file in fls]) if y == True]
    if len(fls) == 0:
        stations = stations.drop(stations[stations['Station'] == station].index)

snames = stations['Station'].unique()
print(snames)
stations.set_index(stations['Station'], inplace=True)
nsites = len(stations)

#snames = np.delete(snames, 6)

output_df = pd.DataFrame()
### Loop over sites
for sitename in snames:
    print('Start processing at ' + sitename + ' station')
    
    lat = stations.loc[sitename, 'Latitude']
    lon = stations.loc[sitename, 'Longitude']
    tile = [stations.loc[sitename, 'tile_h'], stations.loc[sitename, 'tile_v']]
    veg_type = stations.loc[sitename, 'IGBP']
    iveg = igbp_dict[veg_type]
    #iveg = veg_type - 1
    """
    2. ESTIMATION OF HOURLY EVI/LSWI VARIATIONS
    """
    print('getting MODIS for ', sitename, ' station ', year)
    data = get_modis_point(year=year, lat = lat, lon = lon, tile = tile, MODISpath = MODISpath)
    
    
    fjul = (julian(1,1, year)-1) + data[0]
    
    
    fjul_out = (julian(1,1, year)) + np.arange(0,365, step = 1/48)
    data = [fjul, data[1], data[2]]
    
    if np.isnan(data[1]).all():
        data[1][:] = 0.5
        print("all EVI missing for",sitename)
    if np.isnan(data[2]).all():
        data[2][:] = 0.5
        print("all LSWI missing for",sitename)
    EVI = np.empty(shape=(17520))
    LSWI = np.empty(shape=(17520))
    
    
    f = interpolate.interp1d(fjul, data[1], fill_value = 'extrapolate')
    EVI[:] = f(fjul_out)
    f = interpolate.interp1d(fjul, data[2], fill_value = 'extrapolate')
    LSWI[:] = f(fjul_out)
    
    """
    3. INITIALIZATION OF METEOROLOGY
    """
    print('getting met data at ' + sitename + ' station')
    TEMP = np.array([])
    RAD = np.array([])
    if input_origin == 'ERA5':
        for month in range(12):
            if input_origin == 'ERA5':
                met_nc = Dataset(Metpath+'ERA5_'+str(month+1).zfill(2)+'_2015.nc', 'r')
                if month == 0:
                    lat_era5 = np.array(met_nc.variables['latitude'])
                    lat_era5 = lat_era5[::-1] #Define latitudes from lower values to higher values
                    lon_era5 = np.array(met_nc.variables['longitude'])

                    dlat = abs(lat-lat_era5)
                    dlon = abs(lon -lon_era5)
                    sela = np.where(dlat == np.min(dlat))[0][0]
                    selo = np.where(dlon == np.min(dlon))[0][0]
                    if lat_era5[sela] >= lat:
                        if lon_era5[selo] >= lon:
                            ISW = selo -1
                            JSW = sela -1   
                        else:
                            ISW = selo
                            JSW = sela -1
                    else:
                        if lon_era5[selo] >= lon:
                            ISW = selo -1
                            JSW = sela 
                        else:
                            ISW = selo
                            JSW = sela 
                    factorNE = ((lat - lat_era5[JSW])/(lat_era5[JSW+1] - lat_era5[JSW]))*((lon - lon_era5[ISW])/(lon_era5[ISW+1] - lon_era5[ISW]))
                    factorSE = ((lat_era5[JSW + 1] - lat)/(lat_era5[JSW+1] - lat_era5[JSW]))*((lon - lon_era5[ISW])/(lon_era5[ISW+1] - lon_era5[ISW]))
                    factorSW = ((lat_era5[JSW + 1] - lat)/(lat_era5[JSW+1] - lat_era5[JSW]))*((lon_era5[ISW + 1] - lon)/(lon_era5[ISW+1] - lon_era5[ISW]))
                    factorNW = ((lat - lat_era5[JSW])/(lat_era5[JSW+1] - lat_era5[JSW]))*((lon_era5[ISW + 1] - lon)/(lon_era5[ISW+1] - lon_era5[ISW]))
                    
                temp_era5 = np.array(met_nc.variables['t2m']) - 273.15
                
                temp_era5 = temp_era5[:,::-1,:]
                temp_out = factorNE*temp_era5[:,JSW + 1, ISW + 1] + factorNW*temp_era5[:,JSW + 1, ISW] + factorSE*temp_era5[:,JSW, ISW + 1] + factorSW*temp_era5[:,JSW, ISW]
                TEMP = np.concatenate((TEMP, temp_out))

                ssrd_era5 = np.array(met_nc.variables['ssrd'])
                ssrd_era5 = ssrd_era5[:,::-1,:]/3600
                ssrd_out = factorNE*ssrd_era5[:,JSW + 1, ISW + 1] + factorNW*ssrd_era5[:,JSW + 1, ISW] + factorSE*ssrd_era5[:,JSW, ISW + 1] + factorSW*ssrd_era5[:,JSW, ISW]
                RAD = np.concatenate((RAD, ssrd_out))
                met_nc.close()
            elif input_origin == 'WRF':
                dds = monthrange(year, month)[1]
                for dd in range(1, dds + 1):
                    met_nc = Dataset(Metpath+'wrfout_d'+str(wrf_domain).zfill(2)+'_'+str(year)+'-'+str(month).zfill(2) + '-' + str(dd).zfill(2) + '_00:00:00','r') 
                    if month == 0 and dd ==1:
                        lat_wrf = np.array(met_nc.variables['XLAT'])
                        lon_wrf = np.array(met_nc.variables['XLONG'])
                        dist = abs(lat-lat_wrf) + abs(lon-lon_wrf)
                        res = np.where(dist == np.min(dist))
                        sela = res[0][0]
                        selo = res[1][0]
                        if lat_wrf[sela] >= lat:
                            if lon_wrf[selo] >= lon:
                                ISW = selo -1
                                JSW = sela -1   
                            else:
                                ISW = selo
                                JSW = sela -1
                        else:
                            if lon_wrf[selo] >= lon:
                                ISW = selo -1
                                JSW = sela 
                            else:
                                ISW = selo
                                JSW = sela 
                        factorNE = ((lat - lat_wrf[JSW])/(lat_wrf[JSW+1] - lat_wrf[JSW]))*((lon - lon_wrf[ISW])/(lon_wrf[ISW+1] - lon_wrf[ISW]))
                        factorSE = ((lat_wrf[JSW + 1] - lat)/(lat_wrf[JSW+1] - lat_wrf[JSW]))*((lon - lon_wrf[ISW])/(lon_wrf[ISW+1] - lon_wrf[ISW]))
                        factorSW = ((lat_wrf[JSW + 1] - lat)/(lat_wrf[JSW+1] - lat_wrf[JSW]))*((lon_wrf[ISW + 1] - lon)/(lon_wrf[ISW+1] - lon_wrf[ISW]))
                        factorNW = ((lat - lat_wrf[JSW])/(lat_wrf[JSW+1] - lat_wrf[JSW]))*((lon_wrf[ISW + 1] - lon)/(lon_wrf[ISW+1] - lon_wrf[ISW]))
                           
                    temp_wrf = np.array(met_nc.variables['T2']) - 273.15
                    temp_out = factorNE*temp_wrf[:,JSW + 1, ISW + 1] + factorNW*temp_wrf[:,JSW + 1, ISW] + factorSE*temp_wrf[:,JSW, ISW + 1] + factorSW*temp_wrf[:,JSW, ISW]
                    TEMP = np.concatenate((TEMP, temp_out))

                    ssrd_wrf = np.array(met_nc.variables['SWDOWN'])
                    ssrd_out = factorNE*ssrd_wrf[:,JSW + 1, ISW + 1] + factorNW*ssrd_wrf[:,JSW + 1, ISW] + factorSE*ssrd_wrf[:,JSW, ISW + 1] + factorSW*ssrd_wrf[:,JSW, ISW]
                    RAD = np.concatenate((RAD, ssrd_out))
                    met_nc.close()
    
    

    fjul = (julian(1,1, year)) + np.arange(0,365, step = 1/24)
    f = interpolate.interp1d(fjul, TEMP, fill_value = 'extrapolate')
    Temp = f(fjul_out) #Interpolated to flux time steps
    f = interpolate.interp1d(fjul, RAD, fill_value = 'extrapolate')
    Rad = f(fjul_out) #Interpolated to flux time steps
    
    """
    4. ESTIMATION OF MAX/MIN OF EVI/LSWI VARIATIONS
    """
    Evimax = np.max(EVI)
    Evimin = np.min(EVI)
    EviIn = (Evimax - Evimin)
    LSWImax = np.max(LSWI)
    LSWImin = np.min(LSWI)
    
    """
    5. ESTIMATION OF SCALAR EFFECTS ON GPP PRODUCTS
    """
    TMIN = vprmConstants.loc[iveg, 'tempMin']
    TMAX = vprmConstants.loc[iveg, 'tempMax']
    TOPT = vprmConstants.loc[iveg, 'tempOpt']
    
    Tscale = ((Temp - TMIN)*(Temp-TMAX))/(((Temp-TMIN)*(Temp-TMAX))-((Temp-TOPT)*(Temp-TOPT)))
    Tscale[Tscale < 0] = 0
    #modification for so-called "xeric systems", comprising shrublands and grasslands
    #these have different dependencies on ground water.

    
    
    if iveg in [3, 6]:
        Wscale = (LSWI - LSWImin)/(LSWImax - LSWImin)
    else:
        Wscale = (1 + LSWI)/(1 + LSWImax)

    Wscale[Wscale <0] = 0
    Pscale = (1 + LSWI)/2

    if iveg == 0:
        Pscale[:] = 1
        
    if iveg in [1, 2, 3, 5, 7]:
        threshmark = 0.55
        evithresh = Evimin + (threshmark*(Evimax-Evimin))
        phenologyselect = np.where(EVI[:] > evithresh)
        Pscale[phenologyselect] = 1
    Pscale[Pscale < 0] = 0
        #by default, grasslands and savannas never have pScale=1
    """
    6. HOURLY GEE (mol/km2/hr) ESTIMATIONS
    """
    lambdaGPP = vprmConstants.loc[iveg, 'lambdaGPP.sw']
    radZero = vprmConstants.loc[iveg, 'swradZero']
    GEE = lambdaGPP*Tscale*Wscale*Pscale*EVI*Rad/(1 + (Rad/radZero))*(-1)
    
    GEE[GEE > 0] = 0
    GEE = GEE *3600
    
    """
    7. HOURLY RSP (mol/km2/hr)
    """
    
    alpha = vprmConstants.loc[iveg, 'alphaResp']
    beta = vprmConstants.loc[iveg, 'intResp']
    RSP = Temp*alpha + beta
    
    RSP = RSP *3600
    
    NEE = GEE + RSP
    
    if sitename == snames[0]:
        output_df['Times'] = fjul_out
        
    output_df[sitename + '_GEE'] = GEE
    output_df[sitename + '_RSP'] = RSP
    output_df[sitename + '_NEE'] = NEE


output_df.to_csv(outpath+'VPRM.'+tag+'_'+str(year)+'.csv', index = False, header=True)
    
    