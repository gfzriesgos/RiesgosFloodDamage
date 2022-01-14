# -*- coding: utf-8 -*-
"""
Created on Fri Jul 19 11:22:06 2019

@author: fbrill
"""

# only for documentation / transparency
# this script shows the raw hydraulic output is converted to wdmax, vmax, d
# assuming 2 VRT files for all water depth / velocity files respectively

import numpy as np
from osgeo import gdal

mypath = "path/to/hydraulic_rawdata/"


def writeRaster(data, outname, srs, proj, dtype=gdal.GDT_UInt16):
    """
    Exports a 2D dataset as GTiff raster. default dtype is set to GDT_UInt16 -
    this can be any gdal dtype e.g. Float64. srs and proj should be obtained
    from the input file via the .GeoGeoTransform() and .GetProjection()
    """

    if data.ndim != 2:
        print("Provided data is not 2D")

    xs, ys = data.shape
    driver = gdal.GetDriverByName("GTiff")
    outfile = driver.Create(outname, ys, xs, 1, dtype)
    outfile.SetGeoTransform(srs)
    outfile.SetProjection(proj)
    outfile.GetRasterBand(1).WriteArray(data)
    outfile = None


wd = gdal.Open(mypath + "wd.vrt")
v = gdal.Open(mypath + "v.vrt")
wd_array = wd.ReadAsArray()
v_array = v.ReadAsArray()

wdmax = wd_array.max(0)
vmax = v_array.max(0)

wdmaxtime = wd_array.argmax(0)
vmaxtime = v_array.argmax(0)

# some reshaping for proper indexing
flatindex = wdmaxtime.ravel()
vflat = v_array.reshape(v_array.shape[0], v_array.shape[1] * v_array.shape[2])
idx = np.arange(0, vflat.shape[1])
v_at_wdmax = vflat[flatindex, idx].reshape(v_array.shape[1], v_array.shape[2])

# duration - careful about units
binary = wd_array > 0.01  # boolean
d = binary.sum(0)  # True + True = 2

srs = wd.GetGeoTransform()
proj = wd.GetProjection()

writeRaster(wdmax, mypath + "wdmax.tif", srs, proj, gdal.GDT_Float32)
writeRaster(wdmaxtime, mypath + "wdmaxtime.tif", srs, proj)
writeRaster(vmax, mypath + "vmax.tif", srs, proj, gdal.GDT_Float32)
writeRaster(vmaxtime, mypath + "vmaxtime.tif", srs, proj)
writeRaster(v_at_wdmax, mypath + "v_at_wdmax.tif", srs, proj, gdal.GDT_Float32)
writeRaster(d, mypath + "duration_in_nr_of_scenes.tif", srs, proj)
