# -*- coding: utf-8 -*-
"""
Created on Wed Nov  7 13:12:09 2018

@author: fbrill
"""

#             -- Damage estimation for the showcase in Ecuador --             #
# This script assumes all input data to be stored within the same folder. The
#       path to the folder is currently os.path.join(sys.path[0], data) 
#       and all results will be created in the same folder as the input

import os
import sys
import numpy as np
import pandas as pd
from osgeo import gdal, ogr, osr
from geopandas import GeoDataFrame, overlay
from sklearn.externals import joblib


def andes_curve(water_depth):
    """Replication of the SDF provided by the JRC for South America"""
    
    dmg = (1.006049 + (0.001284178 - 1.006049) /
           (1 + (water_depth / 797962.3) ** 0.9707786) ** 681383)
    return(dmg)


def maiwald_schwarz(water_depth, damage_grade):
    """
    This is presented as SDF Type 2 by Maiwald & Schwarz 2008
    to derive relative monetary loss from categorical damage classes
    I am personally not sure whether that concept is useful
    """

    water_depth = water_depth/100                 # formula uses wd in meters!
    a = np.array(damage_grade,  dtype=np.float32)
    b = a.copy()
    a[np.where(damage_grade == 1)] = 1.3
    b[np.where(damage_grade == 1)] = 0.69
    a[np.where(damage_grade == 2)] = 9.7
    b[np.where(damage_grade == 2)] = 0.67
    a[np.where(damage_grade == 3)] = 11.9
    b[np.where(damage_grade == 3)] = 0.74
    a[np.where(damage_grade == 4)] = 12.9
    b[np.where(damage_grade == 4)] = 0.76

    rloss = a * (np.e ** (b * water_depth))
    # maximum is 100% damage + 15% demolition cost
    rloss[rloss > 115] = 115

    return(rloss.round(0)/100)


def addProbaTable(df, classifier, vals, ext='clf', digits=2, threshold=0.5):
    """
    This overwrites the existing object, no assignment needed.
    Using the probability for the most likely class to display confidence
    I consider any visualization beyond 'low' and 'high' as non-serious
    """

    df['MostLikelyClass_'+ext] = classifier.predict(vals)
    proba = classifier.predict_proba(vals)
    df['proba_d1_'+ext] = proba[:, 0].round(digits)
    df['proba_d2_'+ext] = proba[:, 1].round(digits)
    df['proba_d3_'+ext] = proba[:, 2].round(digits)
    df['proba_d4_'+ext] = proba[:, 3].round(digits)

    max_proba = proba.max(axis=1)
    conf = pd.Series(1, range(0, len(max_proba)))
    conf[max_proba > threshold] = 2
    df['confidence_'+ext] = conf.values
    return(df)


if __name__ == "__main__":

    # input
    # mypath                 = sys.argv[1]
    mydir                  = sys.path[0]
    mypath                 = os.path.join(mydir, "data")
    hydraulic_file         = os.path.join(mypath, "vei3_wdmax.tif")
    velocity_file          = os.path.join(mypath, "vei3_vmax.tif")
    duration_file          = os.path.join(mypath, "vei3_duration.tif")
    shapes_name            = os.path.join(mypath, "OBM_subset.geojson")
    manzanas_name          = os.path.join(mypath, "manzanas_scenario.geojson")
    
    # output
    binary_outname         = os.path.join(mypath,"vei3_binary.tif")
    hydraulic_file_cm      = os.path.join(mypath,"vei3_wdmax_cm.tif")
    polygon_name           = os.path.join(mypath,"vei3_binary_polygon.geojson")
    hydraulic_polygons     = os.path.join(mypath,"vei3_wdmax_polygons.geojson")
    velocity_polygons      = os.path.join(mypath,"vei3_velocity_polygons.geojson")
    duration_polygons      = os.path.join(mypath,"vei3_duration_polygons.geojson")
    hazard_name            = os.path.join(mypath,"vei3_hazard.geojson")
    manzanas_overlay_name  = os.path.join(mypath,"vei3_damage_manzanas.geojson")
    damage_name            = os.path.join(mypath,"vei3_damage_buildings.geojson") 
    geopandas_format       = "GeoJSON"                   
    damage_format          = "GeoJSON"
     
    # Read all files
    hydraulic_raw = gdal.Open(hydraulic_file)
    hydraulic_array = hydraulic_raw.ReadAsArray()
    velocity = gdal.Open(velocity_file)
    velocity_band = velocity.GetRasterBand(1)
    duration = gdal.Open(duration_file)
    duration_band = duration.GetRasterBand(1)

    # My own classifers trained on GFZ data
    nb_cm = joblib.load(os.path.join(mypath, "classifiers", "nb_wd_continuous.pkl"))
    nb_all = joblib.load(os.path.join(mypath, "classifiers", "nb4.pkl"))
    rf_all = joblib.load(os.path.join(mypath, "classifiers", "rf4.pkl"))
    mlreg = joblib.load(os.path.join(mypath, "classifiers", "mlreg.pkl"))

    def writeRaster(data, outname, outpath=mypath,
                    ref=hydraulic_raw, dtype=gdal.GDT_Byte):
        """
        Exports a 2D dataset as GTiff raster, using a reference band.
        dtype is set to GDT_Byte - can be any gdal dtype e.g. UInt16
        It would also be possible to set srs and gt without ref
        """

        if hydraulic_raw is None:
            print('Reference File is missing')
        if data.ndim != 2:
            print('Provided data is not 2D')

        xs, ys = data.shape
        driver = gdal.GetDriverByName("GTiff")
        outfile = driver.Create(os.path.join(outpath, outname), ys, xs, 1, dtype)
        outfile.SetGeoTransform(ref.GetGeoTransform())
        outfile.SetProjection(ref.GetProjection())
        outfile.GetRasterBand(1).WriteArray(data)
        outfile = None

# --------------------------------- Binarize ----------------------------------
    # flooded or not
    hydraulic_array[hydraulic_array < 0.0005] = 0
    hydraulic_array[hydraulic_array >= 0.0005] = 1

    writeRaster(hydraulic_array, binary_outname)

    # x100 only if in meters!!
    hydraulic_array = hydraulic_raw.ReadAsArray()
    hydraulic_array[hydraulic_array < 0.0005] = 0
    hydraulic_array = hydraulic_array * 100

    writeRaster(hydraulic_array, hydraulic_file_cm, dtype=gdal.GDT_UInt16)

    print('Step 1 - completed')

# -------------------------------- Polygonize ---------------------------------

    binary = gdal.Open(binary_outname)
    binary_band = binary.GetRasterBand(1)
    binary_array = binary.ReadAsArray()
    cm = gdal.Open(hydraulic_file_cm)                    # !
    cm_band = cm.GetRasterBand(1)

    def PolygonizeToFile(data, mask, outname, fieldname='inundation',
                         outpath=mypath, ref=binary, dtype=ogr.OFTInteger):
        if binary is None:
            print('Reference File is missing')

        driver = ogr.GetDriverByName("GeoJSON")
        outDatasource = driver.CreateDataSource(os.path.join(outpath, outname))
        srs = osr.SpatialReference()
        srs.ImportFromWkt(ref.GetProjectionRef())
        outLayer = outDatasource.CreateLayer(outname.strip('.geojson'), srs=srs)
        newField = ogr.FieldDefn(fieldname, dtype)
        outLayer.CreateField(newField)
        gdal.Polygonize(data, mask, outLayer, 0, [], callback=None)
        outDatasource.Destroy()
        outDatasource = None

    # Overwrite
    if os.path.exists(polygon_name):
        ogr.GetDriverByName("GeoJSON").DeleteDataSource(polygon_name)
    if os.path.exists(hydraulic_polygons):
        ogr.GetDriverByName("GeoJSON").DeleteDataSource(hydraulic_polygons)
    if os.path.exists(velocity_polygons):
        ogr.GetDriverByName("GeoJson").DeleteDataSource(velocity_polygons)
    if os.path.exists(duration_polygons):
        ogr.GetDriverByName("GeoJSON").DeleteDataSource(duration_polygons)

    # Binary Polygon
    PolygonizeToFile(binary_band, binary_band, "binary_test.geojson")

    # WATER DEPTH
    PolygonizeToFile(cm_band, binary_band, hydraulic_polygons, dtype=ogr.OFTReal)

    # VELOCITY
    PolygonizeToFile(velocity_band, binary_band, velocity_polygons, 'velocity')

    # DURATION
    PolygonizeToFile(duration_band, binary_band, duration_polygons, 'duration')

    print('Step 2 - completed')

# ------------------------------- Intersection --------------------------------

    manzanas  = GeoDataFrame.from_file(manzanas_name)
    shapes    = GeoDataFrame.from_file(shapes_name)
    hydraulic = GeoDataFrame.from_file(hydraulic_polygons)
    velocity  = GeoDataFrame.from_file(velocity_polygons)
    duration  = GeoDataFrame.from_file(duration_polygons)

    shapes['shape_id'] = range(0, len(shapes))
    manzanas['manzana_id'] = range(0, len(manzanas))

    # Intersect all the features of interest
    wd_v = overlay(hydraulic, velocity, how="intersection")
    wd_v_d = overlay(wd_v, duration, how="intersection")
    buildings_overlay = overlay(wd_v_d, shapes, how="intersection")
    manzanas_overlay = overlay(wd_v_d, manzanas, how="intersection")

    # aggfunc = mean or maximum / only matters for wd_v_d
    puzzle = buildings_overlay[['shape_id', 'osm_id', 'gem_occupa', 'gem_positi',
                                'Area', 'DegrComp', 'RadGyras', 'inundation',
                                'velocity', 'duration', 'geometry']]
    buildings_overlay = puzzle.dissolve(by='shape_id', aggfunc='max')

    puzzle = manzanas_overlay[['DPA_MAN', 'manzana_id', 'NR_OBM', 'Area_mn',
                               'Area_25', 'Are_mdn', 'Area_75', 'Area_mx',
                               'DgC_mdn', 'RdG_mdn', 'inundation', 'velocity',
                               'duration', 'geometry']]
    manzanas_overlay = puzzle.dissolve(by='manzana_id', aggfunc='mean')

    # crs has to be assigned again in case the data is to be exported
    wd_v.crs = hydraulic.crs
    wd_v_d.crs = hydraulic.crs
    buildings_overlay.crs = shapes.crs
    manzanas_overlay.crs = manzanas.crs
    # wd_v_d.to_file(hazard_name, "GeoJSON")

    print('Step 3 - completed')

# -------------- Apply Classifiers to affected Intersections ------------------

    # Buildings
    wd = buildings_overlay['inundation'].values.reshape(-1, 1)
    vals = buildings_overlay[['inundation', 'velocity', 'duration', 'Area']].copy()

    addProbaTable(buildings_overlay, nb_cm, wd, 'nb_wd')
    addProbaTable(buildings_overlay, nb_all, vals, 'nb_all')
    addProbaTable(buildings_overlay, rf_all, vals, 'rf_all')
    addProbaTable(buildings_overlay, mlreg, vals, 'mlreg')
    buildings_overlay['Stage_Damage_Function'] = andes_curve(wd/100)
    buildings_overlay['ms_rloss'] = maiwald_schwarz(buildings_overlay['inundation'],
                                    buildings_overlay['MostLikelyClass_nb_all'])

    # Manzanas
    wd = manzanas_overlay['inundation'].values.reshape(-1, 1)
    vals = manzanas_overlay[['inundation', 'velocity',
                             'duration', 'Are_mdn']].copy().fillna(value=0)

    addProbaTable(manzanas_overlay, nb_cm, wd, 'nb_wd')
    addProbaTable(manzanas_overlay, nb_all, vals, 'nb_all')
    addProbaTable(manzanas_overlay, rf_all, vals, 'rf_all')
    addProbaTable(manzanas_overlay, mlreg, vals, 'mlreg')
    manzanas_overlay['Stage_Damage_Function'] = andes_curve(wd/100)
    manzanas_overlay['ms_rloss'] = maiwald_schwarz(manzanas_overlay['inundation'],
                                   manzanas_overlay['MostLikelyClass_nb_all'])

    print('Step 4 - completed')

# ---------------------- Re-unify the building shapes -------------------------

    entire_buildings = overlay(buildings_overlay, shapes, how="union")
    entire_buildings = entire_buildings.dissolve(by='shape_id', aggfunc='max')
    entire_buildings.crs = shapes.crs
    entire_buildings = entire_buildings[buildings_overlay.columns]

    entire_buildings.to_file(damage_name, damage_format)
    manzanas_overlay.to_file(manzanas_overlay_name, "GeoJSON")

    print("{} shapes affected".format(len(buildings_overlay)))
    print("DONE")
