# The longitude and latitude coordinates are not ordered the same way
# for all different tools and libraries.
# This script uses (latitude, longitude) as is used by geopy as 
# specified in EPSG:4326
#
#
#

# TODO move all the includes like scipy
# GEOpy or sth that are not needed to their respective functions
import sys
import math
from collections import deque
from PIL import Image, ImageDraw
from geopy.distance import vincenty
from lxml import etree
from xml.etree import cElementTree
import matplotlib.pyplot as plt
from scipy.interpolate import griddata
import numpy as np

class WayNode:
    def __init__(self, id, pos = None, neighbors = None, dist = None):
        self.id = id
        self.pos = pos
        self.in_deque = False
        if neighbors is None:
            self.neighbors = []
        else:
            self.neighbors = neighbors
        if dist is None:
            self.dist = float("inf")
        else:
            self.dist = dist

    def add(self, node):
        for neigh in self.neighbors:
            if neigh.node.id == node.id:
                break
        self.neighbors.append(WayNodeNeighbor(node))

class WayNodeNeighbor:
    """ This classes requires the distance to be safed twice """
    def __init__(self, node, dist = None):
        self.node = node
        self.dist = dist

def exportXML(nodes, center, fname):
    with open(fname, "w") as f:
        f.write("<?xml version='1.0' encoding='UTF-8'?>\n<distance>")
        f.write("<center id='"+str(center.id)+"'></center>\n")
        for i, node in nodes.items():
            f.write("<node id='"+str(node.id)+"' dist='"+str(node.dist)+"' lat='"+str(node.pos[0])+"' lon='"+str(node.pos[1])+"'>\n")
            for neigh in node.neighbors:
                f.write("<neigh id='"+str(neigh.node.id)+"' dist='"+str(neigh.dist)+"'></neigh>\n")
            f.write("</node>\n")
        f.write("</distance>")

def importXML(fname):
    context = cElementTree.iterparse(fname, events=("end","start"))
    nodes = {}
    center = None
    neighbors = None
    for event, element in context:
        if event == "start":
            if element.tag == "neigh":
                neighbors.append(WayNodeNeighbor(int(element.get("id")), float(element.get("dist"))))
            elif element.tag == "center":
                try:
                    center = int(element.get("id"))
                except:
                    print("Center without id")
            elif element.tag == "node":
                neighbors = []
                i = int(element.get("id"))
                dist = float(element.get("dist"))
                pos = (float(element.get("lat")), float(element.get("lon")))
        elif event == "end" and element.tag == "node":
            if element.tag == "node":
                node = WayNode(i, pos, neighbors, dist)
                nodes[i] = node
        element.clear()

    for i, node in nodes.items():
        for neigh in node.neighbors:
            neigh.node = nodes[neigh.node]

    return nodes, nodes[center]

def getAttributes(element):
    for k in element:
        yield element.get(k)

def parseOSM(fname, center = None, waychecker = None):
    """ Parses the ways and nodes of a osm file and returns the center node"""
    nodes = parseWays(fname, waychecker)
    center = parseNodes(fname, nodes, center)
    return (nodes, center)

def findNearest(nodes, pos):
    node_id = None
    node_diff = float("inf")

    for k, node in nodes.items():
        diff = abs(node.pos[0] - center[0]) + abs(node.pos[1] - center[1])
        if diff < node_diff:
            node_diff = diff
            node_id = i

def parseNodes(fname, nodes, center = None):
    """ Adds longitude and latitude to stored nodes, and returns the centering node """
    context = cElementTree.iterparse(fname, events=("end",))

    # First parse lat and lon from all way nodes
    for event, element in context:    
        if element.tag != "node":
            pass
        else:
            i = int(element.get("id"))
            
            if i in nodes:
                node = nodes[i]

                lat = float(element.get("lat"))
                lon = float(element.get("lon"))
                node.pos = (lat, lon)
        # Frees memory
        # TODO look at the other clear in parseWays
        element.clear()

    # Secondly calculate distance for neighbors
    for i, node in nodes.items():
        for neigh in node.neighbors:
            neigh.dist = vincenty(node.pos, neigh.node.pos).meters 

    if center_id is None:
        return nodes, None
    else:
        return nodes[center_id]


def parseWays(fname, waychecker):
    """ Parses all ways and safes the respective nodes and their "neighbors" """
    context = cElementTree.iterparse(fname, events=("start", "end"))

    nodes = {}
    way = None
    backward = True
    use_way = False
    # First just parse the ways
    for event, element in context:
        if way is None and element.tag != "way":
            pass
        elif event == "start":
            if element.tag == "way":
                way = []
                backward = True
                use_way = False
            elif element.tag == "tag":
                if waychecker.check(element.get("k"), element.get("v")):
                    use_way = True
                elif element.get("k") == "oneway":
                    backward = False
            elif element.tag == "nd":
                i = int(element.get("ref"))
                way.append(i)
        elif event == "end" and element.tag == "way":
            if use_way and len(way) > 1:
                last = None
                for i in way:
                    try:
                        node = nodes[i]
                    except KeyError:
                        node = WayNode(i)
                        nodes[i] = node

                    if last is not None:
                        last.add(node)
                        if backward:
                            node.add(last)
                    last = node
            way = None
        # Free memory
        # TODO it says u can even free more here
        # http://stackoverflow.com/questions/4695826/efficient-way-to-iterate-throught-xml-elements
        element.clear()
    return nodes
    
def floodFill(nodes, start = None):
    """ Calculates all the distances to all nodes by using the neighbours """
    queue = deque()
    if start is not None:
        start.dist = 0.
        queue.append(start)

    for i, node in nodes.items():
        if node.dist == 0.:
            queue.append(node)

    for node in shiftDeque(queue):
        node.in_deque = False
        for neigh in node.neighbors:
            dist = neigh.dist + node.dist    
            
            if neigh.node.dist > dist:
                neigh.node.dist = dist
                if not neigh.node.in_deque:
                    queue.append(neigh.node)
                    neigh.node.in_deque = True

def getBounds(nodes):
    # TODO does this work on opposite side of earth
    # as I suppose the map will be mirrored
    minlat = float("inf")
    minlon = float("inf")
    maxlat = float("-inf")
    maxlon = float("-inf")

    for i, node in nodes.items():
        if minlat > node.pos[0]:
            minlat = node.pos[0]
        if maxlat < node.pos[0]:
            maxlat = node.pos[0]
        if minlon > node.pos[1]:
            minlon = node.pos[1]
        if maxlon < node.pos[1]:
            maxlon = node.pos[1]

    return (minlat, minlon), (maxlat, maxlon)

def project(pos, minlat, maxlon, width, height, scale):
    x = width - (maxlon - pos[1]) * 10000 * scale
    y = height + (projectF(minlat) - projectF(pos[0])) * 180/math.pi * 10000 * scale
    return (int(x),int(y))

def sec(lat):
    return 1/math.cos(lat)

def projectF(lat):
    l = lat/180*math.pi
    return math.log(math.tan(l) + sec(l))

def drawContours(nodes, mi, ma, width = 1000, height = None):
    x = []
    y = []
    y2 = []
    z = []
    for i, item in enumerate(nodes.items()):
        k, node = item
        if node.dist == float("inf"):
            continue

        x.append((node.pos[0], node.pos[1]))
        y.append(node.pos[0])
        y2.append(node.pos[1])
        if type(node.dist) != type(float("inf")):
            print(node.dist)
        z.append(node.dist)

    xi, yi = np.mgrid[mi[0]:ma[0]:100j, mi[1]:ma[1]:200j]
    z = np.array(z)
    x = np.array(x)
    max_dist = max(nodes.items(), key=lambda node: node[1].dist if node[1].dist != float("inf") else 0.)
    max_dist = max_dist[1].dist
    zi = griddata(x, z, (xi, yi), method="linear")
    CS = plt.contour(xi, yi, zi, 15, linewidths=0.5, colors='k')
    CS = plt.contourf(xi, yi, zi, 15, cmap=plt.cm.rainbow,
            vmax=max_dist, vmin=0)
    #plt.plot(y,y2, 'k.', ms=1)
    plt.colorbar()  # draw colorbar
    # plot data points.
    plt.xlim(mi[0], ma[0])
    plt.ylim(mi[1], ma[1])
    plt.savefig('foo.png')

def drawGraph(nodes, mi, ma, width = 1000, height = None):
    if width is not None:
        # TODO why 10000
        scale = width / (ma[1] - mi[1]) / 10000
        height = (projectF(ma[0]) - projectF(mi[0])) * 180 / math.pi * 10000 * scale
    elif height is not None:
        # TODO what to do here
        print("Not yet implemented", file=sys.stderr)
        sys.exit(1)
    else:
        print("No size given")
        sys.exit(2)
    
    image = Image.new("RGBA", (int(width), int(height)), (255,255,255,0))
    draw = ImageDraw.Draw(image)
    max_dist = max(nodes.items(), key=lambda node: node[1].dist if node[1].dist != float("inf") else 0.)
    max_dist = max_dist[1].dist
    cfac = 255/max_dist

    for i, node in nodes.items():
        pos = project(node.pos, mi[0], ma[1], width, height, scale)
        if node.dist != float("inf"):
            color = int(node.dist * cfac)
            draw.point(pos, (0, color, 0, 255))
        else:
            draw.point(pos, (255,0,0,255))
    
    del draw
    return image

def drawMapnik():
    pass

class CheckWay:
    def __init__(self):
        self.selector = dict()

    def check(self, k, v):
        try:
            s = self.selector[k]
            return v in s
        except IndexError:
            return False

    def setKey(self, key, value):
        if key not in self.selector:
            self.selector[key] = set()
        self.selector[key].append(value)

    def setCar(self):
        highway = ["motorway", "trunk", "primary", "secondary", "tertiary", 
            "unclassified", "residential", "service", "motorway_link",
            "trunk_link", "primary_link", "secondary_link", "tertiary_link", "road"]
        for h in highway:
            self.setKey("highway", h)

    def setPedestrian(self):
        pedestrian = ["pedestrian", "living_street", "footway", "steps", "path"]
        sidewalk = ["left", "right", "both", "no"]
        for p in pedestrian:
            self.setKey("pedestrian", p)

        for s in sidewalk:
            self.setKey("sidewalk", s)

    def setBicycle(self):
        self.highway.append("cycleway")
        cycleway = ["lane", "opposite", "opposite_lane", "track" "opposite_track", "share_busway", "shared_lane"]
        for c in cycleway:
            self.setKey("cycleway", c)
        
def shiftDeque(d):
    """ always returns the first element of deque """
    while True:
        try:
            yield d.popleft()
        except IndexError:
            break

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Calculates distance maps")
    parser.add_argument("-f", "--file", help="OSM File to be parsed")
    parser.add_argument("-o", "--output", help="File name of output, with extension")
    parser.add_argument("-F", "--format", help="The format for export")
    parser.add_argument("-W", "--width", type=int, help="The width of the image")
    parser.add_argument("-H", "--height", type=int, help="The height of the image")
    parser.add_argument("--lon", type=float, help="Set the longitude of start position")
    parser.add_argument("--lat", type=float, help="Set the latitude of start position")
    parser.add_argument("-i", "--interpolate", type=int, help="Defines the distance after which \"new\" nodes are added")
    parser.add_argument("--export", help="Tell python to pickle the calculated nodes to a file", dest="expor")
    parser.add_argument("--import", action='append', help="Tell python to import a pickled file", dest="impor")
    parser.add_argument("--import-with-nearest", help="If more import files are used each node is interpolated")
    parser.add_argument("--pedestrian", action='store_const', const=True, help="Select pedestrian road")
    parser.add_argument("--car", action='store_const', const=True, help="Select motorways")
    parser.add_argument("--bicycle", action='store_const', const=True, help="Select roads for bicycle use")
    parser.add_argument("--add-selector", action="append", help="Add a key/value pair, for selecting the ways")
    parser.add_argument("--add-score", action="append", help="Adds a score to a certain key/value pair")
    parser.add_argument("--unit", help="Uses this unit instead of meters")
    args = parser.parse_args()
    
    if args.impor is None:
        if args.file is None:
            print("No input file specified, use -f/--file", file=sys.stderr)
            sys.exit(1)

        # Get waychecker
        waychecker = WayChecker()
        if args.pedestrian:
            waychecker.setPedestrian()
        if args.car:
            waychecker.setCar()
        if args.bicycle:
            waychecker.setBicycle()

        for l in args.add_selector:
            try:
                k, v = l.split(" ")
                waychecker.setKey(k, v)
            except ValueError:
                pass

        # First parse file
        nodes, center = parseOSM(args.file, (args.lat, args.lon), waychecker)
        print("Parsed File:", args.file)
    else:
        nodes = {} 
        center = None
        for fname in args.impor:
            n, center = importXML(fname)
            nodes.update(n)

            if center is not None:
                center = center
            print("Imported File:", fname)

    # Calculate dists
    #floodFill(nodes, center)

    # if export specified first export
    if args.expor is not None:
        exportXML(nodes, center, args.expor)
        print("Exported Result to:", args.expor)
    
    if args.format in ("png","jpg","gif","tiff"):
        mi, ma = getBounds(nodes)
        drawContours(nodes, mi, ma, args.width, args.height)
        image = drawGraph(nodes, mi, ma, args.width, args.height)
        with open(args.output, "wb") as f:
            image.save(f, args.format)
        print("Drawed Image", args.output)

    else:
        # TODO implement
        print("Not yet implemented", file=sys.stderr)
        sys.exit(1)
