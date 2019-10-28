FROM ubuntu:18.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install python3 git python3-scipy python3-numpy python3-gdal python3-pip libspatialindex-dev zip -y

WORKDIR /usr/share/git/riesgos_flooddamage

COPY requirements.txt .

RUN pip3 install -r requirements.txt

COPY . .

RUN cd showcase_ecuador && \
    unzip data.zip && \
    rm data.zip && \
    rm data/duration_h.tif data/vmax_ms.tif data/wdmax_cm.tif
