#!BPY

""" Registration info for Blender menus:
Name: 'OGRE (.mesh.xml)...'
Blender: 236
Group: 'Import'
Tip: 'Import an Ogre-Mesh (.mesh.xml) file.'
"""

__author__ = "Daniel Wickert"
__version__ = "0.4.1 10/29/09"

__bpydoc__ = """\
This script imports Ogre-Mesh models into Blender.

Supported:<br>
    * multiple submeshes (triangle list)
    * uvs
    * materials (textures only)
    * vertex colours

Missing:<br>
    * submeshes provided as triangle strips and triangle fans
    * materials (diffuse, ambient, specular, alpha mode, etc.)
    * skeletons
    * animations

Known issues:<br>
    * blender only supports a single uv set, always the first is taken
      and only the first texture unit in a material, even if it is not for
      the first uv set.
    * code is a bit hacky in parts.
"""

# Copyright (c) 2005-2009 Daniel Wickert
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.


import Blender
import glob
import os
import re
import xml.sax
import xml.sax.handler

# determines the verbosity of loggin.
#   0 - no logging (fatal errors are still printed)
#   1 - standard logging
#   2 - verbose logging
#   3 - debug level. really boring (stuff like vertex data and verbatim lines)
IMPORT_LOG_LEVEL = 1

IMPORT_SCALE_FACTOR = 1.0
IMPORT_OGREXMLCONVERTER = "OgreXmlConverter.exe"

def log(msg):
    if IMPORT_LOG_LEVEL >= 1: print msg

def vlog(msg):
    if IMPORT_LOG_LEVEL >= 2: print msg

def dlog(msg):
    if IMPORT_LOG_LEVEL >= 3: print msg

class Mesh:
    def __init__(self):
        self.submeshes = []
        self.vertices = []
        self.vertexcolours = []
        self.normals = []
        self.uvs = []
    
class Submesh:
    def __init__(self):
        self.vertices = []
        self.vertexcolours = []
        self.normals = []
        self.faces = []
        self.uvs = []
        self.indextype = ""
        self.materialname = ""
        self.sharedvertices = 0

class Material:
    def __init__(self, name):
        self.name = name
        self.texname = ""
        self.diffuse = (1.0, 1.0, 1.0, 1.0)
        self.ambient = (1.0, 1.0, 1.0, 1.0)
        self.specular = (0.0, 0.0, 0.0, 0.0)
        self.blenderimage = 0
        self.loading_failed = 0

    def getTexture(self):
        if self.blenderimage == 0 and not self.loading_failed:
            try:
                f = file(self.texname, 'r')
                f.close()
                self.blenderimage = Blender.Image.Load(self.texname)
            except IOError, (errno, strerror):
                errmsg = "Couldn't open %s #%s: %s" \
                        % (self.texname, errno, strerror)
                log(errmsg)
                self.loading_failed = 1;
                
        return self.blenderimage


class OgreMeshSaxHandler(xml.sax.handler.ContentHandler):
    
    global IMPORT_SCALE_FACTOR
    
    def __init__(self):
        self.mesh = 0
        self.submesh = 0
        self.ignore_input = 0
        self.load_next_texture_coords = 0

    def startDocument(self):
        self.mesh = Mesh()
        
    def startElement(self, name, attrs):
        
        if name == 'sharedgeometry':
            self.submesh = self.mesh

        if name == 'submesh':
            self.submesh = Submesh()
            self.submesh.materialname = attrs.get('material', "")
            self.submesh.indextype = attrs.get('operationtype', "")
            if attrs.get('usesharedvertices') == 'true':
                self.submesh.sharedvertices = 1
        
        if name == 'vertex':
            self.load_next_texture_coords = 1

        if name == 'face' and self.submesh:
            face = (
                int(attrs.get('v1',"")),
                int(attrs.get('v2',"")),
                int(attrs.get('v3',""))
            )
            self.submesh.faces.append(face)
        
        if name == 'position':
            vertex = (
                #Ogre x/y/z --> Blender x/-z/y
                float(attrs.get('x', "")) * IMPORT_SCALE_FACTOR,
                -float(attrs.get('z', "")) * IMPORT_SCALE_FACTOR,
                float(attrs.get('y', "")) * IMPORT_SCALE_FACTOR
            )
            self.submesh.vertices.append(vertex)
               
        if name == 'normal':
            normal = (
                #Ogre x/y/z --> Blender x/-z/y
                float(attrs.get('x', "")),
                -float(attrs.get('z', "")),
                float(attrs.get('y', ""))
            )
            self.submesh.normals.append(normal)
        
        if name == 'texcoord' and self.load_next_texture_coords:
            uv = (
                float(attrs.get('u', "")),
                # flip vertical value, Blender's 0/0 is lower left
                # whereas Ogre's 0/0 is upper left
                1.0 - float(attrs.get('v', ""))
            )
            self.submesh.uvs.append(uv)
            self.load_next_texture_coords = 0

        if name == 'colour_diffuse':
            self.submesh.vertexcolours.append(attrs.get('value', "").split())
            
    def endElement(self, name):
        if name == 'submesh':
            self.mesh.submeshes.append(self.submesh)
            self.submesh = 0


def CreateBlenderMesh(name, mesh, materials):
    bmesh = Blender.NMesh.GetRaw()

    # dict matname:blender material
    bmaterials = {}
    bmat_idx = -1

    log("Mesh with %d shared vertices." % len(mesh.vertices))
    vertex_count = len(mesh.vertices)
    for i in range(0, vertex_count):
        ogre_v = mesh.vertices[i]
        dlog("   vertex %d with XYZ: %f %f %f" %\
                (i, ogre_v[0], ogre_v[1], ogre_v[2]))
        blender_v = Blender.NMesh.Vert(ogre_v[0], ogre_v[1], ogre_v[2])
        
        if len(mesh.normals):
            # Set the normals
            blender_v.no[0] = mesh.normals[i][0]
            blender_v.no[1] = mesh.normals[i][1]
            blender_v.no[2] = mesh.normals[i][2]

        if len(mesh.uvs):
            # Set the sticky per vertex uvs
            blender_v.uvco[0] = mesh.uvs[i][0]
            blender_v.uvco[1] = mesh.uvs[i][1]
            
        bmesh.verts.append(blender_v)
        
    
    submesh_count = len(mesh.submeshes)
    vertex_offset = 0
    for j in range(0, submesh_count):
        submesh = mesh.submeshes[j]
        if materials.has_key(submesh.materialname):
            omat = materials[submesh.materialname]
            bmat = 0
            if (not bmaterials.has_key(omat.name)):
                bmat = create_blender_material(omat)
                bmaterials[submesh.materialname] = bmat
                bmesh.addMaterial(bmat)
            else:
                bmat = bmaterials[submesh.materialname]
            bmat_idx = bmesh.materials.index(bmat)
        else:
            omat = 0
            bmat = 0
            bmat_idx = -1
        log("Submesh %d with %d vertices and %d faces..." % \
                (j, len(submesh.vertices), len(submesh.faces)))
        
        # transfer vertices
        vertex_count = len(submesh.vertices)
        for i in range(0, vertex_count):
            ogre_v = submesh.vertices[i]
            blender_v = Blender.NMesh.Vert(ogre_v[0], ogre_v[1], ogre_v[2])

            if len(submesh.normals):
                # Set the normals
                blender_v.no[0] = submesh.normals[i][0]
                blender_v.no[1] = submesh.normals[i][1]
                blender_v.no[2] = submesh.normals[i][2]

            if len(submesh.uvs):
                # Set the sticky per vertex uvs
                blender_v.uvco[0] = submesh.uvs[i][0]
                blender_v.uvco[1] = submesh.uvs[i][1]
            
            bmesh.verts.append(blender_v)

        # transfer faces
        face_count = len(submesh.faces)
        
        # decide whether to take colours and uvs from shared buffer or
        # from the submesh
        faces = submesh.faces
        if submesh.sharedvertices == 1:
            uvs = mesh.uvs
            vertexcolours = mesh.vertexcolours
        else:
            uvs = submesh.uvs
            vertexcolours = submesh.vertexcolours
            
        for i in range(0, face_count):
            ogre_f = submesh.faces[i]
            
            dlog("face %d : %f/%f/%f" % (i, ogre_f[0], ogre_f[1], ogre_f[1]))
            
            f = Blender.NMesh.Face()
            if omat and omat.getTexture():
                f.mode |= Blender.NMesh.FaceModes['TEX']
                f.image = omat.getTexture()
            if bmat:
                f.materialIndex = bmat_idx

            f.v.append(bmesh.verts[ogre_f[0] + vertex_offset])
            f.v.append(bmesh.verts[ogre_f[1] + vertex_offset])
            f.v.append(bmesh.verts[ogre_f[2] + vertex_offset])
            if len(uvs):
                f.uv.append(uvs[ogre_f[0]])
                f.uv.append(uvs[ogre_f[1]])
                f.uv.append(uvs[ogre_f[2]])
            if len(submesh.vertexcolours):
                f.mode |= Blender.NMesh.FaceModes['SHAREDCOL']
                for k in range(3):
                    col = Blender.NMesh.Col()
                    col.r = int(float(vertexcolours[ogre_f[k]][0])*255.0)
                    col.g = int(float(vertexcolours[ogre_f[k]][1])*255.0)
                    col.b = int(float(vertexcolours[ogre_f[k]][2])*255.0)
                    col.a = 255
                    f.col.append(col)

            bmesh.faces.append(f)
        
        # vertices of the new submesh are appended to the NMesh's vertex buffer
        # this offset is added to the indices in the index buffer, so that
        # the right vertices are indexed
        vertex_offset += vertex_count

        log("done.")
        
    # bmesh.hasVertexUV(len(submesh.uvs))
    # TODO: investigate and fix
    # Why oh why ain't this line working...
    # bmesh.hasFaceUV(len(submesh.uvs))
    # ...have to hard set it.
    bmesh.hasFaceUV(1)

    # create the mesh
    object = Blender.Object.New('Mesh', name)
    object.link(bmesh)
    return object

def convert_meshfile(filename):
    if IMPORT_OGREXMLCONVERTER != '':
        commandline = IMPORT_OGREXMLCONVERTER + ' "' + filename + '"'
        log("executing %s..." % commandline)
        os.system(commandline)
        log("done.")

def collect_materials(dirname):
    # preparing some patterns
    #    to collect the material name
    matname_pattern = re.compile('^\s*material\s+(.*?)\s*$')
    #    to collect the texture name
    texname_pattern = re.compile('^\s*texture\s+(.*?)\s*$')
    #    to collect the diffuse colour
    diffuse_alpha_pattern = re.compile(\
            '^\s*diffuse\s+([^\s]+?)\s+([^\s]+?)\s+([^\s]+?)\s+([^\s]+).*$')
    diffuse_pattern = re.compile(\
            '^\s*diffuse\s+([^\s]+?)\s+([^\s]+?)\s+([^\s]+).*$')
    #    to collect the specular colour
    specular_pattern = re.compile(\
            '^\s*specular\s+([^\s]+?)\s+([^\s]+?)\s+([^\s]+).*$')

    # the dictionary where to put the materials
    materials = {}

    # for all lines in all material files..
    material_files = glob.glob(dirname + '/*.material')
    material = 0
    for filename in material_files:
        f = file(filename, 'r')
        line_number = 0
        for line in f:
            try:
                line_number = line_number + 1
                dlog("line to be matched: %s" % line)
                
                m = matname_pattern.match(line)
                if m:
                    material = Material(m.group(1))
                    materials[material.name] = material
                    vlog("parsing material %s" % m.group(1))
                m = texname_pattern.match(line)
                # load only the first texture unit's texture
                # TODO change to use the first one using the first uv set
                if m and not material.texname:
                    material.texname = dirname + '/' + m.group(1)
                m = diffuse_alpha_pattern.match(line)
                if not m:
                    m = diffuse_pattern.match(line)
                if m:
                    vlog("    parsing diffuse..")
                    groups = m.groups()
                    r = float(groups[0])
                    g = float(groups[1])
                    b = float(groups[2])
                    #TODO: alpha still untested
                    if len(groups) > 3:
                        a = float(groups[3])
                    else:
                        a = 1.0
                    
                    material.diffuse = (r, g, b, a)
                    vlog("   diffuse: %s" % str(material.diffuse))
                m = specular_pattern.match(line)
                if m:
                    vlog("    parsing specular..")
                    groups = m.groups()
                    r = float(groups[0])
                    g = float(groups[1])
                    b = float(groups[2])
                    
                    material.specular = (r, g, b, 1.0)
                    vlog("   specular: %s" % str(material.specular))
            except Exception, e:
                log("    error parsing material %s in %s on line % d: " % \
                    (material.name, filename, line_number))
                log("        exception: %s" % str(e))
    return materials
            

def create_blender_material(omat):
    bmat = Blender.Material.New(omat.name)
    bmat.rgbCol = (omat.diffuse[0], omat.diffuse[1], omat.diffuse[2])
    bmat.specCol = (omat.specular[0], omat.specular[1], omat.specular[2])
    bmat.alpha = omat.diffuse[3]

    img = omat.getTexture()
    if img:
        tex = Blender.Texture.New(omat.texname)
        tex.setType('Image')
        tex.setImage(omat.getTexture())

        bmat.setTexture(0, tex, Blender.Texture.TexCo.UV,\
                Blender.Texture.MapTo.COL)
    
    return bmat

def fileselection_callback(filename):
    log("Reading mesh file %s..." % filename)
    
    # is this a mesh file instead of an xml file?
    if (filename.lower().find('.xml') == -1):
        # No. Use the xml converter to fix this
        log("No mesh.xml file. Trying to convert it from binary mesh format.")
        convert_meshfile(filename)
        filename += '.xml'

    dirname = Blender.sys.dirname(filename)
    basename = Blender.sys.basename(filename)
    
    # parse material files and make up a dictionary: {mat_name:material, ..}
    materials = collect_materials(dirname)
    
    # prepare the SAX parser and parse the file using our own content handler
    parser = xml.sax.make_parser()   
    handler = OgreMeshSaxHandler()
    parser.setContentHandler(handler)
    parser.parse(open(filename))
    
    # create the mesh from the parsed data and link it to a fresh object
    scene = Blender.Scene.GetCurrent()
    meshname = basename[0:basename.lower().find('.mesh.xml')]
    object = CreateBlenderMesh(meshname, handler.mesh, materials)
    scene.link(object)
    object.select(True)

    log("import completed.")
    
    Blender.Redraw()

Blender.Window.FileSelector(fileselection_callback, "Import OGRE", "*.xml")

