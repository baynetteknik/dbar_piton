import struct
import zlib
import os

exe_path = r"C:\Users\alp\AppData\Local\DIAApp3-x64\DIAApp3.exe"
with open(exe_path, "rb") as f:
    data = f.read()

cookie = b"MEI\x0c\x0b\x0a\x0b\x0e"
pos = data.rfind(cookie)
magic, length, toc_pos, toc_len, pyvers, pylibname = struct.unpack("!8siiii64s", data[pos:pos+88])

arch_start = pos - length
f_toc = data[arch_start + toc_pos : arch_start + toc_pos + toc_len]
try:
    f_toc_decomp = zlib.decompress(f_toc)
    print("Decompressed TOC len:", len(f_toc_decomp))
    f_toc = f_toc_decomp
except Exception as e:
    print("Zlib decomp failed:", e)

# In PyInstaller 6+, the TOC entries might be:
# entry_len(i), e_pos(q or i), e_len(q or i), e_ulen(q or i), e_cflag(b), e_typ(b), name(s)
offset = 0
toc_entries = []
while offset < len(f_toc):
    try:
        (entry_len,) = struct.unpack("!i", f_toc[offset:offset+4])
        entry_data = f_toc[offset:offset+entry_len]
        offset += entry_len
        # Try 64-bit unpack (entry_len(4), pos(8), len(8), ulen(8), cflag(1), typ(1), name)
        # or 32-bit unpack (entry_len(4), pos(4), len(4), ulen(4), cflag(1), typ(1), name)
        if entry_len >= 30: # 4 + 8*3 + 2 = 30
            e_pos, e_len, e_ulen, e_cflag, e_typ = struct.unpack("!qqqBB", entry_data[4:30])
            e_name = entry_data[30:].decode("utf-8", errors="ignore").rstrip("\x00")
        else:
            e_pos, e_len, e_ulen, e_cflag, e_typ = struct.unpack("!iiiBB", entry_data[4:18])
            e_name = entry_data[18:].decode("utf-8", errors="ignore").rstrip("\x00")
        toc_entries.append((e_name, chr(e_typ) if 32 <= e_typ <= 126 else str(e_typ), e_pos, e_len, e_ulen, e_cflag))
    except Exception as e:
        print(f"Error parsing entry at offset {offset}: {e}")
        break

print(f"Total TOC entries: {len(toc_entries)}")
for e in toc_entries:
    print(f"Name: {e[0]}, Type: {e[1]}, Pos: {e[2]}, Len: {e[3]}, ULen: {e[4]}")
    if "PYZ" in e[0] or e[0].endswith(".pyz"):
        pyz_raw = data[arch_start + e[2] : arch_start + e[2] + e[3]]
        if e[5] == 1:
            pyz_raw = zlib.decompress(pyz_raw)
        with open("scratch/pyz_extracted.pyz", "wb") as out:
            out.write(pyz_raw)
        print("WROTE PYZ archive, size:", len(pyz_raw))
