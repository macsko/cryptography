import zipfile
import struct
import argparse
import shutil

EXTRA_PREFIX = 0x3333

def batch_copy(src, dst, size=16*1024*1024, limit=None):
    src_read = src.read
    dst_write = dst.write
    if limit is None:
        limit = float("inf")
    while True:
        res = src_read(min(size, limit))
        if not res:
            return
        dst_write(res)
        limit -= min(size, limit)

def hide_in_extra(zip_filename, text):
    with open(zip_filename, "rb") as zin:
        erd = zipfile._EndRecData(zin)
        offset = erd[zipfile._ECD_OFFSET]

        zin.seek(offset)
        centdir = zin.read(zipfile.sizeCentralDir)
        centdir = list(struct.unpack(zipfile.structCentralDir, centdir))
        filename = zin.read(centdir[zipfile._CD_FILENAME_LENGTH])
        extra = zin.read(centdir[zipfile._CD_EXTRA_FIELD_LENGTH])

        full_text = struct.pack('<HH', EXTRA_PREFIX, len(text)) + text
        extra += full_text
        
        centdir[zipfile._CD_EXTRA_FIELD_LENGTH] += len(full_text)
        erd[zipfile._ECD_SIZE] += len(full_text)

        new_erd = struct.pack(zipfile.structEndArchive, *erd[:zipfile._ECD_COMMENT])
        new_cd = struct.pack(zipfile.structCentralDir, *centdir)

        file_cd_size = zipfile.sizeCentralDir + centdir[zipfile._CD_FILENAME_LENGTH] + centdir[zipfile._CD_EXTRA_FIELD_LENGTH]
        old_file_cd_size = file_cd_size - len(full_text)

        with open(zip_filename, 'r+b') as zout:
            # Write old central directory skipping first file header
            zin.seek(offset + old_file_cd_size)
            zout.seek(offset + file_cd_size)
            batch_copy(zin, zout, limit=erd[zipfile._ECD_SIZE] - file_cd_size)

            # Write modified central directory file header
            zout.seek(offset)
            zout.write(new_cd)
            zout.write(filename)
            zout.write(extra)

            # Write modified end of central directory
            zout.seek(erd[zipfile._ECD_LOCATION] + len(full_text))
            zout.write(new_erd)

def hide(zip_filename, text):
    with open(zip_filename, "rb") as zin:
        erd = zipfile._EndRecData(zin)
        offset = erd[zipfile._ECD_OFFSET]
        
        text_len = struct.pack("<L", len(text))
        full_text = text + text_len
        
        erd[zipfile._ECD_OFFSET] += len(full_text)
        new_erd = struct.pack(zipfile.structEndArchive, *erd[:zipfile._ECD_COMMENT])
        
        with open(zip_filename, 'r+b') as zout:
            # Write whole old central directory in moved position
            zin.seek(offset)
            zout.seek(offset + len(full_text))
            batch_copy(zin, zout, limit=erd[zipfile._ECD_SIZE])
            
            # Write modified end of central directory
            zout.seek(erd[zipfile._ECD_LOCATION] + len(full_text))
            zout.write(new_erd)
            
            # Write text before central directory
            zout.seek(offset)
            zout.write(full_text)

def parse_command_line():
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_filename", help="Name of input zip file")
    parser.add_argument("-o", help="Name of output zip file", metavar="result_zip_filename")
    parser.add_argument("-f", help="File to be hidden into zip", metavar="filename")
    parser.add_argument("-t", help="Text to be hidden into zip", metavar="text")
    parser.add_argument("-e", help="Hide in extra field", action="store_true")
    return parser.parse_known_args()[0]
                
if __name__ == '__main__':
    args = parse_command_line()
    zip_filename = args.zip_filename
    hide_func = hide
    if args.o:
        # Copy all zip contents
        shutil.copy(zip_filename, args.o)
        zip_filename = args.o
    if args.e:
        hide_func = hide_in_extra
    if args.f is not None:
        with open(args.f, "rb") as f:
            data = f.read()
        hide_func(zip_filename, data)
    elif args.t is not None:
        hide_func(zip_filename, args.t.encode())
    else:
        print("Either -f or -t flag should be specified")
