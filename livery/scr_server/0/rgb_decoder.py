##
# we are going to decode the .rgb file so i can write a decoder in rust
# im better in python thats why im decoding it here

import struct
# struct needed for big endian conversion to int, str etc

"""
https://paulbourke.net/dataformats/sgirgb/

------ SGI Header info

 Size   Type    Name       Description   
 
      2 bytes  short   MAGIC      IRIS image file magic number
                                  This should be decimal 474
      1 byte   char    STORAGE    Storage format
                                  0 for uncompressed
                                  1 for RLE compression
      1 byte   char    BPC        Number of bytes per pixel channel 
                                  Legally 1 or 2
      2 bytes  ushort  DIMENSION  Number of dimensions
                                  Legally 1, 2, or 3
                                  1 means a single row, XSIZE long
                                  2 means a single 2D image
                                  3 means multiple 2D images
      2 bytes  ushort  XSIZE      X size in pixels 
      2 bytes  ushort  YSIZE      Y size in pixels 
      2 bytes  ushort  ZSIZE      Number of channels
                                  1 indicates greyscale
                                  3 indicates RGB
                                  4 indicates RGB and Alpha
      4 bytes  long    PIXMIN     Minimum pixel value
                                  This is the lowest pixel value in the image
      4 bytes  long    PIXMAX     Maximum pixel value
                                  This is the highest pixel value in the image
      4 bytes  char    DUMMY      Ignored
                                  Normally set to 0
     80 bytes  char    IMAGENAME  Image name
                                  Must be null terminated, therefore at most 79 bytes
      4 bytes  long    COLORMAP   Colormap ID
                                  0 - normal mode
                                  1 - dithered, 3 mits for red and green, 2 for blue, obsolete
                                  2 - index colour, obsolete
                                  3 - not an image but a colourmap
    404 bytes  char    DUMMY      Ignored
                                  Should be set to 0, makes the header 512 bytes.

"""

with open("car1-ow1.rgb", 'rb') as f:
    magic_bytes = f.read(2)
    magic = struct.unpack(">h", magic_bytes)[0]
    print(f"Magic = {magic}")

    # now we fill in for the rest of the spec
    storage_byte = f.read(1)
    storage = struct.unpack(">B", storage_byte)[0]
    print(f"Storage = {storage}")

    bpc_byte = f.read(1)
    bpc = struct.unpack(">B", bpc_byte)[0]
    print(f"BPC = {bpc}")

    dimension_bytes = f.read(2)
    dimension = struct.unpack(">H", dimension_bytes)[0]
    print(f"Dimension = {dimension}")

    xsize_bytes = f.read(2)
    xsize = struct.unpack(">H", xsize_bytes)[0]
    print(f"XSize = {xsize}")

    ysize_bytes = f.read(2)
    ysize = struct.unpack(">H", ysize_bytes)[0]
    print(f"YSize = {ysize}")

    zsize_bytes = f.read(2)
    zsize = struct.unpack(">H", zsize_bytes)[0]
    print(f"ZSize = {zsize}")

    pixmin_bytes = f.read(4)
    pixmin = struct.unpack(">i", pixmin_bytes)[0]
    print(f"PixMin = {pixmin}")

    pixmax_bytes = f.read(4)
    pixmax = struct.unpack(">i", pixmax_bytes)[0]
    print(f"PixMax = {pixmax}")

    # Skip 4 bytes of dummy data
    f.read(4)

    imagename_bytes = f.read(80)
    ## print(f"ImageName Bytes = {imagename_bytes}")
    imagename = imagename_bytes.rstrip(b'\x00').decode('ascii', errors='ignore')
    print(f"ImageName = '{imagename}'")

    colormap_bytes = f.read(4)
    colormap = struct.unpack(">i", colormap_bytes)[0]
    print(f"Colormap = {colormap}")

    # Skip 404 bytes of dummy data
    dummy_bytes = f.read(404)
    if dummy_bytes != b'\x00' * 404:
        print("Warning: Dummy bytes are not all zero!")

    print("\n--- Header decoded successfully ---")