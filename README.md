OSM distance calculator
=======================

This project creates isochrones based on osm files.
It is based on this http://wiki.openstreetmap.org/wiki/Distance_maps Article
And reimplements code from http://wiki.openstreetmap.org/wiki/Distancemap.pl this script and others.
It's not based on pgroute and should be easy to use without much to be included or installed.


Current State
==============

The project itself is far from complete but I hope to implement most of the functionality soon.


Aims / Features
===============

1. Create distances from ways in osm data
2. Select and exclude certain ways based on mode of travel
3. Add scores to different types of ways to export distance in time
4. Include distances based on different sources (i.e. public transport)
5. Calculate distances based on one or more start points
6. Export contours and or gradient maps
7. Calculate unconnected nodes
8. Export real map with the contour or gradient overlay
9. Probable implement it scalable for huge number of nodes (i.e. entire countries)
10. Make it a python package 
