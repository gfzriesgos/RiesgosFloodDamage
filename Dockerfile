FROM ubuntu:18.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install python3 git python3-scipy python3-numpy python3-gdal python3-pip libspatialindex-dev zip -y

RUN pip3 install sklearn scikit-learn==0.19.1 geopandas==0.5.0 Rtree==0.8.3

RUN mkdir /usr/share/git

RUN cd /usr/share/git && \
    git clone --depth 1 -b master https://github.com/ruester/RiesgosFloodDamage.git riesgos_flooddamage && \
    cd riesgos_flooddamage/showcase_ecuador && \
    unzip data.zip
