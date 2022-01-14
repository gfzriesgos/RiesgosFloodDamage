# -*- coding: utf-8 -*-
"""
Created on Wed Nov  7 13:12:09 2018

@author: fbrill
"""

#             -- Damage estimation for the showcase in Ecuador --             #
# This script assumes all input data to be stored within the same folder. The
#       path to the folder is currently os.path.join(sys.path[0], data)
#       and all results will be created in the same folder as the input
#                water depth should be in cm and dtype UInt16

import os
import sys
import functools
import numpy as np
import pandas as pd
from osgeo import gdal, ogr, osr
from geopandas import GeoDataFrame, overlay
from sklearn.externals import joblib


def writeRaster(data, outname, srs, proj, dtype=gdal.GDT_Byte):
    """
    Exports a 2D dataset as GTiff raster. default dtype is set to GDT_Byte -
    this can be any gdal dtype e.g. UInt16. srs and proj should be obtained
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


def polygonizeToFile(
    data,
    mask,
    outname,
    outpath,
    projref,
    fieldname="inundation",
    dtype=ogr.OFTInteger,
):
    """
    A binary mask has to be provided to restrict polygonization.
    Otherwise this process would polygonize every raster cell.
    projref should be obtained via .GeoProjectionRef()
    """

    driver = ogr.GetDriverByName("GeoJSON")
    outDatasource = driver.CreateDataSource(os.path.join(outpath, outname))
    srs = osr.SpatialReference()
    srs.ImportFromWkt(projref)
    outLayer = outDatasource.CreateLayer(outname.strip(".geojson"), srs=srs)
    newField = ogr.FieldDefn(fieldname, dtype)
    outLayer.CreateField(newField)
    gdal.Polygonize(data, mask, outLayer, 0, [], callback=None)
    outDatasource.Destroy()
    outDatasource = None


def addProbaTable(df, classifier, vals, ext="clf", digits=2, threshold=0.3):
    """
    This overwrites the existing object, no assignment needed.
    Using the probability for the most likely class to display confidence
    I consider any visualization beyond 'low' and 'high' as non-serious
    """

    df["MostLikelyClass_" + ext] = classifier.predict(vals)
    proba = classifier.predict_proba(vals)
    df["proba_d1_" + ext] = proba[:, 0].round(digits)
    df["proba_d2_" + ext] = proba[:, 1].round(digits)
    df["proba_d3_" + ext] = proba[:, 2].round(digits)
    df["proba_d4_" + ext] = proba[:, 3].round(digits)

    max_proba = pd.DataFrame(np.sort(proba)[:, -2:], columns=["2nd", "1st"])
    dif_proba = max_proba["1st"].values - max_proba["2nd"].values
    conf = pd.Series(1, range(0, len(dif_proba)))
    conf[dif_proba > threshold] = 2

    df["proba_strdmg_" + ext] = 1 - df["proba_d1_" + ext]
    df["confidence_" + ext] = conf.values

    return df


def JRC_SDF(water_depth):
    """Replication of the SDF provided by the JRC for South America"""

    dmg = (
        1.006049
        + (0.001284178 - 1.006049)
        / (1 + (water_depth / 797962.3) ** 0.9707786) ** 681383
    )
    return dmg


def maiwald_schwarz(water_depth, damage_grade):
    """
    This is presented as SDF Type 2 by Maiwald & Schwarz 2008
    to derive relative monetary loss from categorical damage classes
    I am personally not sure whether that concept is useful
    """

    water_depth = water_depth / 100  # formula uses wd in meters!
    a = np.array(damage_grade, dtype=np.float32)
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
    # maximum in the original is 115% (100% damage + 15% demolition cost)
    rloss[rloss > 100] = 100
    # my dmg4 is actually dmg5 and always 100 anyway
    # rloss[np.where(damage_grade == 4)] = 100

    return rloss.round(0) / 100


def try_with_postfix(column, postfix="_1"):
    """
    Return the column name with a postfix.
    The method is intended to be a fallback mode
    for `find_matching_column_names`.
    Parameters:
    - `column`: name of the column.
    - `postfix`: postfix to add to the column name
    """

    return column + postfix


def find_matching_column_names(from_dataframe, in_dataframe, fallback_mode):
    """
    Return a list of column names that are used in the
    from_dataframe and should be matched in the in_dataframe.
    It is intended to be a replacement if something like this
    entire_buildings = entire_buildings[buildings_overlay.columns]
    fails, because of some renaming in a step before.
    In the normal case the column name just match in both
    dataframes, but if there is a difference (say a _1 and _2 postfix
    in the from_dataframe) then this code has a fallback mode and
    can be used to find this columns too.
    There is a warning for each column that can't be found in the in_dataframe.
    Parameters:
    - `from_dataframe`: dataframe that give the column names that should be used
    - `in_dataframe`: dataframe of which the column names should be used later
    - `fallback_mode`: function to modify the column name to find it in the in_dataframe (for example to add a postfix)
    """

    cols_from = from_dataframe.columns
    set_cols_in = set(in_dataframe.columns)

    result = []

    for c in cols_from:
        if c in set_cols_in:
            result.append(c)
        else:
            c_fallback = fallback_mode(c)
            if c_fallback in set_cols_in:
                result.append(c_fallback)
            else:
                warnings.warn('column "' + c + '" could not be found.')
    return result


if __name__ == "__main__":

    # input
    mydir = sys.path[0]  # use sys.argv[1] ?
    mypath = os.path.join(mydir, "data")
    waterdepth_file = os.path.join(mypath, "wdmax_cm.tif")
    velocity_file = os.path.join(mypath, "vmax_ms.tif")
    duration_file = os.path.join(mypath, "duration_h.tif")
    shapes_name = os.path.join(mypath, "OSM_Ecuador.geojson")
    manzanas_name = os.path.join(mypath, "Manzanas_Ecuador.geojson")

    # output
    binary_outname = os.path.join(mypath, "binary.tif")
    binary_polyname = os.path.join(mypath, "binary_polygon.geojson")
    waterdepth_polyname = os.path.join(mypath, "wdmax_polygons.geojson")
    velocity_polyname = os.path.join(mypath, "vmax_polygons.geojson")
    duration_polyname = os.path.join(mypath, "duration_polygons.geojson")
    damage_manzanas_name = os.path.join(mypath, "damage_manzanas.geojson")
    damage_buildings_name = os.path.join(mypath, "damage_buildings.geojson")

    # Read all files
    waterdepth = gdal.Open(waterdepth_file)
    waterdepth_array = waterdepth.ReadAsArray()
    waterdepth_band = waterdepth.GetRasterBand(1)
    velocity = gdal.Open(velocity_file)
    velocity_band = velocity.GetRasterBand(1)
    duration = gdal.Open(duration_file)
    duration_band = duration.GetRasterBand(1)

    # The CRS of the rasters does not matter as long as it is identical for all
    # Transformation to 4326 is done later since it is easier in geopandas
    if not (
        waterdepth.GetProjection()
        == velocity.GetProjection()
        == duration.GetProjection()
    ):
        raise SystemExit("Provided rasters are not in the same projection")

    # Will be used for writing output files to same extent
    srs = waterdepth.GetGeoTransform()
    proj = waterdepth.GetProjection()

    # My own classifers trained on GFZ data
    decisionFunction = joblib.load(
        os.path.join(mypath, "classifiers", "decisionfunction")
    )

    # --------------------------------- Binarize ----------------------------------
    # flooded or not - file is now considered to be in cm !!
    waterdepth_array[waterdepth_array <= 2] = 0
    waterdepth_array[waterdepth_array == 65535] = 0  # nodata value
    waterdepth_array[waterdepth_array > 2] = 1
    writeRaster(waterdepth_array, binary_outname, srs, proj)
    print("Binarize - completed (1/5)")

    # -------------------------------- Polygonize ---------------------------------

    binary = gdal.Open(binary_outname)
    binary_band = binary.GetRasterBand(1)
    binary_array = binary.ReadAsArray()

    # Overwrite - should also be done for buildings/manzanas
    if os.path.exists(binary_polyname):
        ogr.GetDriverByName("GeoJSON").DeleteDataSource(binary_polyname)
    if os.path.exists(waterdepth_polyname):
        ogr.GetDriverByName("GeoJSON").DeleteDataSource(waterdepth_polyname)
    if os.path.exists(velocity_polyname):
        ogr.GetDriverByName("GeoJson").DeleteDataSource(velocity_polyname)
    if os.path.exists(duration_polyname):
        ogr.GetDriverByName("GeoJSON").DeleteDataSource(duration_polyname)
    if os.path.exists(damage_manzanas_name):
        ogr.GetDriverByName("GeoJSON").DeleteDataSource(damage_manzanas_name)
    if os.path.exists(damage_buildings_name):
        ogr.GetDriverByName("GeoJSON").DeleteDataSource(damage_buildings_name)

    projref = binary.GetProjectionRef()

    # Binary Polygon
    polygonizeToFile(
        binary_band, binary_band, binary_polyname, mydir, projref, "affected"
    )
    # WATER DEPTH
    polygonizeToFile(
        waterdepth_band,
        binary_band,
        waterdepth_polyname,
        mydir,
        projref,
        "inundation",
        dtype=ogr.OFTReal,
    )
    # VELOCITY
    polygonizeToFile(
        velocity_band,
        binary_band,
        velocity_polyname,
        mydir,
        projref,
        "velocity",
    )
    # DURATION
    polygonizeToFile(
        duration_band,
        binary_band,
        duration_polyname,
        mydir,
        projref,
        "duration",
    )

    print("Polygonize - completed (2/5)")

    # ------------------------------- Intersection --------------------------------

    manzanas = GeoDataFrame.from_file(manzanas_name)
    shapes = GeoDataFrame.from_file(shapes_name)
    waterdepth_poly = GeoDataFrame.from_file(waterdepth_polyname)
    velocity_poly = GeoDataFrame.from_file(velocity_polyname)
    duration_poly = GeoDataFrame.from_file(duration_polyname)

    # transform everything to 4326 regardless
    # manzanas = manzanas.to_crs({'init': 'epsg:4326'})
    # shapes = shapes.to_crs({'init': 'epsg:4326'})
    # waterdepth_poly = waterdepth_poly.to_crs({'init': 'epsg:4326'})
    # velocity_poly = velocity_poly.to_crs({'init': 'epsg:4326'})
    # duration_poly = duration_poly.to_crs({'init': 'epsg:4326'})

    velocity_poly.velocity = velocity_poly.velocity.replace(
        65535, 0.1
    )  # nodata
    velocity_poly.velocity = velocity_poly.velocity / 100
    duration_poly.duration = duration_poly.duration.replace(65535, 0.1)
    duration_poly.duration = duration_poly.duration / 6  # 10min intervals to h
    duration_poly.duration = duration_poly.duration.replace(0, 0.1)
    duration_poly.duration = np.log(duration_poly.duration)

    shapes["shape_id"] = range(0, len(shapes))
    manzanas["manzana_id"] = range(0, len(manzanas))

    # Intersect all the features of interest
    wd_v = overlay(waterdepth_poly, velocity_poly, how="intersection")
    wd_v_d = overlay(wd_v, duration_poly, how="intersection")
    buildings_overlay = overlay(wd_v_d, shapes, how="intersection")
    manzanas_overlay = overlay(wd_v_d, manzanas, how="intersection")

    # aggfunc = mean or maximum / only matters for wd_v_d
    buildings_overlay = buildings_overlay[
        [
            "shape_id",
            "osm_id",
            "area",
            "inundation",
            "velocity",
            "duration",
            "geometry",
        ]
    ].dissolve(by="shape_id", aggfunc="max")

    # buildings_overlay = puzzle.dissolve(by='shape_id', aggfunc='max')

    manzanas_overlay = manzanas_overlay[
        [
            "DPA_MAN",
            "manzana_id",
            "NR_OBM",
            "area_mn",
            "area_25",
            "are_mdn",
            "area_75",
            "area_mx",
            "inundation",
            "velocity",
            "duration",
            "geometry",
        ]
    ].dissolve(by="manzana_id", aggfunc="mean")
    # manzanas_overlay = puzzle.dissolve(by='manzana_id', aggfunc='mean')

    # crs has to be assigned again in case the data is to be exported
    # maybe there should be a check of CRS and whether all are identical
    wd_v.crs = waterdepth_poly.crs
    wd_v_d.crs = waterdepth_poly.crs
    buildings_overlay.crs = shapes.crs
    manzanas_overlay.crs = manzanas.crs

    print("Intersection - completed (3/5)")

    # -------------- Apply Classifiers to affected Intersections ------------------

    # Buildings
    bwd = buildings_overlay[["inundation"]]
    bvals = buildings_overlay[
        ["inundation", "velocity", "duration", "area"]
    ].copy()

    # only one decision function left in this version
    addProbaTable(buildings_overlay, decisionFunction, bvals, "predicted")

    buildings_overlay["SDF_JRC"] = JRC_SDF(bwd / 100)
    buildings_overlay["SDF2_MS"] = maiwald_schwarz(
        buildings_overlay["inundation"],
        buildings_overlay["MostLikelyClass_predicted"],
    )

    # Manzanas
    mwd = manzanas_overlay[["inundation"]]
    mvals = (
        manzanas_overlay[["inundation", "velocity", "duration", "are_mdn"]]
        .copy()
        .fillna(value=0)
    )

    addProbaTable(manzanas_overlay, decisionFunction, mvals, "predicted")

    manzanas_overlay["SDF_JRC"] = JRC_SDF(mwd / 100)
    manzanas_overlay["SDF2_MS"] = maiwald_schwarz(
        manzanas_overlay["inundation"],
        manzanas_overlay["MostLikelyClass_predicted"],
    )

    print("Classification - completed (4/5)")

    # ---------------------- Re-unify the building shapes -------------------------

    shapes = shapes.drop(["osm_id", "area"], axis=1)
    entire_buildings = overlay(buildings_overlay, shapes, how="union")
    entire_buildings = entire_buildings.dissolve(by="shape_id", aggfunc="max")
    entire_buildings.crs = shapes.crs

    # common_cols = find_matching_column_names(
    # from_dataframe=buildings_overlay,
    # in_dataframe=entire_buildings,
    # fallback_mode=functools.partial(try_with_postfix, postfix='_1')
    # )

    # entire_buildings = entire_buildings[common_cols]

    # reduce the size of result by excluding unaffected buildings
    entire_buildings = entire_buildings.dropna(
        subset=["MostLikelyClass_predicted"]
    )

    entire_buildings.to_file(damage_buildings_name, "GeoJSON")
    manzanas_overlay.to_file(damage_manzanas_name, "GeoJSON")

    print("Dissolve - completed (5/5)")
    print("{} shapes affected".format(len(buildings_overlay)))
    print("DONE")
