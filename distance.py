# The longitude and latitude coordinates are not ordered the same way
# for all different tools and libraries.
# This script uses (latitude, longitude) as is used by geopy as 
# specified in EPSG:4326
#
#
#

import sys
from collections import deque
from PIL import Image, ImageDraw
from geopy.distance import vincenty
from lxml import etree
from xml.etree import cElementTree

class WayNode:
    def __init__(self, id, neighbors = None, dist = None):
        self.id = id
        if neighbors is None:
            self.neighbors = []
        else:
            self.neighbors = neighbors
        self.pos = None
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
        f.write("<?xml version='1.0' encoding='UTF-8'?><distance>")
        f.write("<center id='"+str(center.id)+"'></center>")
        for i, node in nodes.items():
            f.write("<node id='"+str(node.id)+"' dist='"+str(node.dist)+"'>")
            for neigh in node.neighbors:
                f.write("<neigh id='"+str(neigh.node.id)+"' dist='"+str(neigh.dist)+"'></neigh>")
            f.write("</node>")
        f.write("</distance>")

def importXML(fname):
    context = cElementTree.iterparse(fname, events=("end",))
    nodes = {}
    center = None
    neighbors = None
    for event, element in context:
        if event == "start" and element.tag == "node":
            neighbors = []
            i = int(element.get("id"))
            dist = float(element.get("dist"))
        elif event == "end":
            if element.tag == "node":
                node = WayNode(i, neighbors, dist)
            elif element.tag == "neigh":
                neighbors.append(WayNodeNeighbor(int(element.get("id")), float(element.get("dist"))))
            elif element.tag == "center":
                center = int(element.get("id"))
        element.clear()

    for node in nodes:
        for neigh in node.neighbors:
            neigh.node = nodes[neigh.node]

    return nodes, nodes[center]

def getAttributes(element):
    for k in element:
        yield element.get(k)

def parseOSM(fname, center = None):
    """ Parses the ways and nodes of a osm file and returns the center node"""
    nodes = parseWays(fname)
    print("Got", len(nodes), "Nodes")
    center = parseNodes(fname, nodes, center)
    return (nodes, center)

def parseNodes(fname, nodes, center = None):
    """ Adds longitude and latitude to stored nodes, and returns the centering node """
    context = cElementTree.iterparse(fname, events=("end",))

    center_pos = 0
    center_id = None
    center_diff = float("inf")
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

                # TODO use the next way node or create nodes self
                if center is not None:
                    diff = abs(lat - center[0]) + abs(lon - center[1])
                    if diff < center_diff:
                        center_diff = diff
                        center_pos = (lat, lon)
                        center_id = i
            
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


def parseWays(fname):
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
                if element.get("k") == "highway":
                    use_way = True
                if element.get("k") == "oneway":
                    backward = False

                # TODO check for different way types
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

def shiftDeque(deque):
    """ always returns the first element of deque """
    while True:
        try:
            yield deque.popLeft()
        except:
            break
    
def floodFill(nodes, start):
    """ Calculates all the distances to all nodes by using the neighbours """
    queue = deque()
    start.dist = 0.
    queue.append(start)

    for node in shiftDeque(queue):
        for neigh in node.neighbors:
            dist = neigh.dist + node.dist    
            
            if neigh.node.dist > dist:
                neigh.node.dist = dist
                queue.append(neigh.node)

def getBounds(nodes):
    # TODO does this work on opposite side of earth
    # as I suppose the map will be mirrored
    minlat = float("inf")
    minlon = float("inf")
    maxlat = float("-inf")
    maxlon = float("-inf")

    for node in nodes:
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
    return (x,y)

def projectF(lat):
    l = lat/180*math.pi
    return math.log(math.tan(lat) + math.sec(lat))

def drawGraph(nodes, mi, ma, width = 1000, height = None):
    if width is not None:
        # TODO why 10000
        scale = width / (ma[1] - mi[1]) / 10000
        height = (projectF(ma[0]) - ProjectF(mi[0])) * 180 / math.pi * 10000 * scale
    elif height is not None:
        # TODO what to do here
        print("Not yet implemented", file=sys.stderr)
        sys.exit(1)
    else:
        print("No size given")
        sys.exit(2)
    
    image = Image.new("RGBA", size, (255,255,255,0))
    draw = ImageDraw.Draw(image)
    max_dist = max(nodes, lambda node: node.dist if node.dist != float("inf") else 0.)
    cfac = 255/max_dist

    for node in nodes:
        pos = project(node.pos, mi[0], ma[1], width, height, scale)
        if node.dist != float("inf"):
            color = node.dist * cfac
            draw.point(pos, (0, color, 0, 255))
        else:
            draw.point(pos, (255,0,0,255))
    
    del draw
    return image

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
    parser.add_argument("--import", help="Tell python to import a pickled file", dest="impor")
    args = parser.parse_args()
    
    if args.impor is None:
        if args.file is None:
            print("No input file specified, use -f/--file", file=sys.stderr)
            sys.exit(1)

        # First parse file
        nodes, center = parseOSM(args.file, (args.lat, args.lon))
        print("Parsed File:", args.file)
    else:
        nodes, center = importXML(args.impor)
        print("Imported File:", args.impor)

    if center is None:
        print("No start point specified, use --lat and --lon")
        sys.exit(1)

    print(center)
    # Calculate dists
    floodFill(nodes, center)

    # if export specified first export
    if args.expor is not None:
        exportXML(nodes, center, args.expor)
        print("Exported Result to:", args.expor)

    if args.format in ("png","jpg","gif","tiff"):
        mi, ma = getBounds(nodes)
        image = drawGraph(nodes, mi, ma, args.width, args.height)
        with open(args.output, "w") as f:
            image.save(sys.stdout, args.format)
        print("Drawed Image", args.output)

    else:
        # TODO implement
        print("Not yet implemented", file=sys.stderr)
        sys.exit(1)
