FROM ubuntu:18.04

ENV DEBIAN_FRONTEND=noninteractive
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

RUN apt-get update && \
    apt-get install -y \
        python3 \
        git \
        cython \
        python3-scipy \
        python3-numpy \
        python3-gdal \
        python3-pip \
        libspatialindex-dev \
        libgdal-dev \
        zip

WORKDIR /usr/share/git/riesgos_flooddamage

COPY requirements.txt .

RUN pip3 install wheel && \
    GDAL_VERSION=$(gdal-config --version) && \
    sed -i -e "s@GDAL==.*@GDAL==$GDAL_VERSION@" requirements.txt && \
    pip3 install -r requirements.txt && \
    pip3 uninstall -y GDAL && \
    pip3 install \
        GDAL==${GDAL_VERSION} \
        --global-option=build_ext \
        --global-option="-I/usr/include/gdal"

COPY . .

RUN cd showcase_ecuador && \
    unzip data.zip && \
    rm data.zip
