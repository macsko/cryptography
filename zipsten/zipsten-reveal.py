import zipfile
import struct
import argparse
import os

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

def reveal(zip_filename, remove=False):
    with open(zip_filename, "rb") as z:
        erd = zipfile._EndRecData(z)
        
        offset = erd[zipfile._ECD_OFFSET]
        z.seek(offset - 4)
        text_len_bytes = z.read(4)
        text_len = struct.unpack("<L", text_len_bytes)[0]
        z.seek(offset - text_len - 4)
        
        result = z.read(text_len)
        
        if remove:
            with open(zip_filename, "r+b") as zout:
                # Move central directory to overwrite the hidden data
                z.seek(offset)
                zout.seek(offset - text_len - 4)
                batch_copy(z, zout, limit=erd[zipfile._ECD_LOCATION] - erd[zipfile._ECD_OFFSET])
                zout.truncate()
                
                # Write modified end of central direcotry
                erd[zipfile._ECD_OFFSET] -= (text_len + 4)
                new_erd = struct.pack(zipfile.structEndArchive, *erd[:zipfile._ECD_COMMENT])
                zout.write(new_erd)

        return result
            
def parse_command_line():
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_filename", help="Name of input zip file")
    parser.add_argument("-f", help="Write result to specified file", metavar="filename")
    parser.add_argument("-t", help="Print result on stdout", action="store_true")
    parser.add_argument("-r", help="Remove hidden data from zip", action="store_true")
    return parser.parse_known_args()[0]
                
if __name__ == '__main__':
    args = parse_command_line()
    data = reveal(args.zip_filename, args.r)
    if data is None:
        print("Hidden data not found")
        os.exit(1)
    if args.f is not None:
        with open(args.f, "wb") as f:
            f.write(data)
    elif args.t:
        print(data.decode())
    else:
        print("Either -f or -t flag should be specified")
