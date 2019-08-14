
# short script for computing OSM statistics per manzana 
# - currently only using the area

library(sf)
library(reshape2)

osm = read_sf("path/to/data")
regions = sf::read_sf("path/to/data")

# actually most shape parameters have been computed by a QGIS-Python Skript
osm$area = st_area(osm)

osm_per_block = list()
for (i in 1:nrow(regions)){
  osm_per_block[[i]] = sf::st_intersects(regions[i,], osm)
}

osmlist = lapply(osm_per_block, unlist) %>% melt
osmlist$manzana = regions$DPA_MANZAN[mylist$L1]

osmlist$area = obm$area[osmlist$value]
# osmlist$occupancy  = osm$gem_occupa[osmlist$value]
# osmlist$floorspace = osm$floor_spac[osmlist$value]
# osmlist$Perimeter  = osm$Perimeter[osmlist$value]
# osmlist$DegrComp   = osm$DegrComp[osmlist$value]
# osmlist$PARatio    = osm$PARatio[osmlist$value]
# osmlist$ShapeIndex = osm$ShapeIndex[osmlist$value]
# osmlist$FracDimInd = osm$FracDimInd[osmlist$value]
# osmlist$RadGyras   = osm$RadGyras[osmlist$value]
# osmlist$geom       = osm$geometry[osmlist$value]
#write.csv(osmlist, "osmlist.csv")

out = osmlist %>% dplyr::group_by(manzana) %>%
                  dplyr::summarize(area_min=min(area),
                                   area_25=quantile(area, 0.25),
                                   area_median=median(area),
                                   area_75=quantile(area, 0.75),
                                   area_max=max(area),
                                   NR_OBM=length(area))

regions = left_join(regions, out, by=c("DPA_MANZAN" = "manzana"))
write_sf(regions, "outname.shp")