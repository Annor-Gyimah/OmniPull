#!/bin/bash

# Set the package name and version
PACKAGE_NAME="omnipull_v"
VERSION="2.0.0"
DESCRIPTION="An open source (Internet Download Manager) with multi-connections and high-speed engine."

# Run the fpm command to create the .deb package
fpm -s dir -t deb -n $PACKAGE_NAME -v $VERSION --description "$DESCRIPTION" --prefix / -C package

