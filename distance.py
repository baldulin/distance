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


class WayNode:
    def __init__(self, id, neighbors = None):
        self.id = id
        self.neighbors = neighbors
        self.pos = None
        self.dist = float(inf)

    def add(self, node):
        self.neighbors.append(node)

class WayNodeNeighbor:
    """ This classes requires the distance to be safed twice """
    def __init__(self, node, dist = None):
        self.node = node
        self.dist = dist

def getAttributes(element):
    for k in element:
        yield element.get(k)

def parseOSM(fname, center = None):
    """ Parses the ways and nodes of a osm file and returns the center node"""
    nodes = parseWays(fname)
    center = parseNodes(fname, nodes, center)
    return (nodes, center)

def parseNodes(fname, nodes, center = None):
    """ Adds longitude and latitude to stored nodes, and returns the centering node """
    context = etree.iterparse(fname, events=("end",), tag="node")

    center_pos = 0
    center_id = None
    center_diff = float("inf")
    # First parse lat and lon from all way nodes
    for event, element in context:    
        if i in nodes:
            node = nodes[i]

            i = int(element.get("id"))
            lat = float(element.get("lat"))
            lon = float(element.get("lon"))
            node.pos = (lat, lon)

            # TODO use the next way node or create nodes self
            if center_lon is not none and center_lat is not None:
                diff = abs(lat - center[0]) + abs(lon - center_lon[1])
                if diff < center_diff:
                    center_diff = diff
                    center_pos = (lat, lon)
                    center_id = i
            
        # Frees memory
        # TODO look at the other clear in parseWays
        element.clear()

    del context

    # Secondly calculate distance for neighbors
    for node in nodes:
        for neigh in node.neighbors:
            neigh.dist = vincenty(node.pos, neigh.node.pos).meters 

    if i is None:
        return None
    else:
        return nodes[i]


def parseWays(fname):
    """ Parses all ways and safes the respective nodes and their "neighbors" """
    context = etree.iterparse(fname, events=("end",), tag="way")

    nodes = {}
    # First just parse the ways
    for event, element in context:
        for elm in element.iterchildren():
            way = []
            backward = True
            use_way = False
            if elm.tag == "tag":
                if elm.get("k") == "highway":
                    use_way = True
                if elm.get("k") == "oneway":
                    backward = False

                # TODO check for different way types
            elif elm.tag == "nd":
                i = int(elm.get("ref"))
                way.append(i)
        
        if use_way and len(way) > 1:
            last = None
            for i in way:
                try:
                    node = nodes[i]
                except KeyError:
                    node = WayNode(i)
                    nodes[i] = node

                if last is not None:
                    last.add(WayNodeNeighbor(node))
                if backward:
                    node.add(WayNodeNeighbor(last))
                last = node
        
        # Free memory
        # TODO it says u can even free more here
        # http://stackoverflow.com/questions/4695826/efficient-way-to-iterate-throught-xml-elements
        element.clear()

    del context
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
    parser.add_argument("-W", "--width", help="The width of the image")
    parser.add_argument("-H", "--height", help="The height of the image")
    parser.add_argument("--lon", help="Set the longitude of start position")
    parser.add_argument("--lat", help="Set the latitude of start position")
    parser.add_argument("-i", "--interpolate", help="Defines the distance after which \"new\" nodes are added")
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
        import pickle
        nodes, center = pickle.load(open(args.impor, "rb"))
        print("Imported File:", args.impor)

    if center is None:
        print("No start point specified, use --lat and --lon")
        sys.exit(1)
    
    # Calculate dists
    floodFill(nodes, center)

    # if export specified first export
    if args.expor is not None:
        import pickle
        pickle.dump((nodes, center), open("save.p", "wb"))
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
