import zipfile
import struct
import argparse
import shutil

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
    return parser.parse_known_args()[0]
                
if __name__ == '__main__':
    args = parse_command_line()
    zip_filename = args.zip_filename
    if args.o:
        # Copy all zip contents
        shutil.copy(zip_filename, args.o)
        zip_filename = args.o
    if args.f is not None:
        with open(args.f, "rb") as f:
            data = f.read()
        hide(zip_filename, data)
    elif args.t is not None:
        hide(zip_filename, args.t.encode())
    else:
        print("Either -f or -t flag should be specified")
