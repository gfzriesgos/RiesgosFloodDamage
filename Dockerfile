FROM ubuntu:18.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install python3 git python3-scipy python3-numpy python3-gdal python3-pip libspatialindex-dev zip -y && \
    pip3 install sklearn scikit-learn==0.19.1 geopandas==0.5.0 Rtree==0.8.3

WORKDIR /usr/share/git/riesgos_flooddamage
COPY . .

RUN cd showcase_ecuador && \
    unzip data.zip
