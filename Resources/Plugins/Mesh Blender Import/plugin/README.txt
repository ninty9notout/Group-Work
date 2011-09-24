Overview
========

The ogre_import.py script can import Ogre meshes with their materials into Blender.

The following Ogre mesh features are supported:
    * single or multiple submeshes (triangle list)
    * shared vertex buffers
    * texture coordinates
    * materials
    * vertex colours

TODO:
    * submeshes provided as triangle strips and triangle fans
    * skeletons
    * animations


Instructions
============

Just copy the script into your .blender/scripts directory and restart blender.
You should now have the option to import ogre meshes under File->Import.
The importer expects the material script(s) and all used textures to be in the
same directory as your mesh.

Note that you need Python 2.3.x for it to work. After installing python
create an environment variable called PYTHON that contains the full path to
your python.exe
("C:\python23\python.exe" for the default installation destination).


In the script itself three options are defined:

* IMPORT_LOG_LEVEL: this option determines the verbosity of loggin.
      The following levels are used:
          0 - no logging (fatal errors are still printed)
          1 - standard logging
          2 - verbose logging
          3 - debug level. (really boring)

* IMPORT_SCALE_FACTOR: this scales the mesh with the given factor,
  default is 0.1

* IMPORT_OGREXMLCONVERTER: this is the path to your copy of the
  OgreXMLConverter, if given and valid, you can import meshes directly
  instead of converting them beforehand to mesh.xml files

Feedback and support
====================

Questions, feature requests and bugreport are best posted to this thread:
http://www.ogre3d.org/phpBB2/viewtopic.php?t=9135

This is still a very early version, so your mesh might not work.
If it doesn't, I'd like to receive error reports, best with your meshes,
or hints on what your meshes include (like multiple submeshes, with some
of them containing vertex colours others not and such).
And please make sure to post the error messages from the blender
console window.

