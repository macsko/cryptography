import zipfile
import struct
import argparse

EXTRA_PREFIX = 0x3333
EXTRA_PREFIX_LEN = 4
TEXT_SIZE_LEN = 4

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

def find_hidden_in_extra(extra):
    i = 0
    while i < len(extra):
        prefix, length = struct.unpack('<HH', extra[i: i + EXTRA_PREFIX_LEN])
        if prefix == EXTRA_PREFIX:
            return extra[i + EXTRA_PREFIX_LEN: i + EXTRA_PREFIX_LEN + length], extra[:i] + extra[i + EXTRA_PREFIX_LEN + length:]
        i += length + EXTRA_PREFIX_LEN
    return None, extra

def reveal_from_extra(zip_filename, remove=False):
    with open(zip_filename, "rb") as z:
        erd = zipfile._EndRecData(z)
        offset = erd[zipfile._ECD_OFFSET]
        z.seek(offset)

        centdir = z.read(zipfile.sizeCentralDir)
        centdir = list(struct.unpack(zipfile.structCentralDir, centdir))
        filename = z.read(centdir[zipfile._CD_FILENAME_LENGTH])
        extra = z.read(centdir[zipfile._CD_EXTRA_FIELD_LENGTH])

        result, old_extra = find_hidden_in_extra(extra)
        if result is None:
            return None

        if remove:
            full_result_len = len(result) + EXTRA_PREFIX_LEN
        
            centdir[zipfile._CD_EXTRA_FIELD_LENGTH] -= full_result_len
            erd[zipfile._ECD_SIZE] -= full_result_len

            new_erd = struct.pack(zipfile.structEndArchive, *erd[:zipfile._ECD_COMMENT])
            new_cd = struct.pack(zipfile.structCentralDir, *centdir)

            file_cd_size = zipfile.sizeCentralDir + centdir[zipfile._CD_FILENAME_LENGTH] + centdir[zipfile._CD_EXTRA_FIELD_LENGTH]
        
            with open(zip_filename, "r+b") as zout:
                # Write modified central directory file header
                zout.seek(offset)
                zout.write(new_cd)
                zout.write(filename)
                zout.write(old_extra)

                #Write old central directory skipping first file header
                batch_copy(z, zout, limit=erd[zipfile._ECD_SIZE] - file_cd_size)

                # Write modified end of central directory
                zout.seek(erd[zipfile._ECD_LOCATION] - full_result_len)
                zout.write(new_erd)
                zout.truncate()
        
        return result

def reveal(zip_filename, remove=False):
    with open(zip_filename, "rb") as z:
        erd = zipfile._EndRecData(z)
        
        offset = erd[zipfile._ECD_OFFSET]
        z.seek(offset - TEXT_SIZE_LEN)
        text_len_bytes = z.read(TEXT_SIZE_LEN)
        text_len = struct.unpack("<L", text_len_bytes)[0]
        if offset - text_len - TEXT_SIZE_LEN < 0:
            return None
        z.seek(offset - text_len - TEXT_SIZE_LEN)
        
        result = z.read(text_len)
        
        if remove:
            with open(zip_filename, "r+b") as zout:
                # Move central directory to overwrite the hidden data
                z.seek(offset)
                zout.seek(offset - text_len - TEXT_SIZE_LEN)
                batch_copy(z, zout, limit=erd[zipfile._ECD_LOCATION] - erd[zipfile._ECD_OFFSET])
                
                # Write modified end of central direcotry
                erd[zipfile._ECD_OFFSET] -= (text_len + TEXT_SIZE_LEN)
                new_erd = struct.pack(zipfile.structEndArchive, *erd[:zipfile._ECD_COMMENT])
                zout.write(new_erd)
                zout.truncate()

        return result
            
def parse_command_line():
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_filename", help="Name of input zip file")
    parser.add_argument("-f", help="Write result to specified file", metavar="filename")
    parser.add_argument("-t", help="Print result on stdout", action="store_true")
    parser.add_argument("-r", help="Remove hidden data from zip", action="store_true")
    parser.add_argument("-e", help="Reveal from extra field", action="store_true")
    return parser.parse_known_args()[0]
                
if __name__ == '__main__':
    args = parse_command_line()
    reveal_func = reveal
    if args.e:
        reveal_func = reveal_from_extra
    data = reveal_func(args.zip_filename, args.r)
    if data is None:
        print("Hidden data not found")
        exit(1)
    if args.f is not None:
        with open(args.f, "wb") as f:
            f.write(data)
    elif args.t:
        print(data.decode())
    else:
        print("Either -f or -t flag should be specified")
