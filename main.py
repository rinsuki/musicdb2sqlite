#!/usr/bin/env python3
from io import BytesIO
import sys
from Crypto.Cipher import AES
from struct import unpack, calcsize
import zlib
import sqlite3
import os
import json

FOURCC = b"hfma"
UTF16_COLUMNS_ALBUM = {
    300: "title",
    301: "artist",
    302: "album_artist",
}
UTF16_COLUMNS_ARTIST = {
    400: "name",
    401: "name_for_sort",
}
UTF16_COLUMNS_TRACK = {
    0x2: "title",
    0x3: "album",
    0x4: "artist",
    0x5: "genre",
    0x6: "localized_file_type",
    0x8: "comment",
    0xc: "composer",
    0x12: "description",
    0x1B: "album_artist",
    0x1E: "title_for_sort",
    0x1F: "album_for_sort",
    0x20: "artist_for_sort",
    0x21: "album_artist_for_sort",
    0x22: "composer_for_sort",
    0x2b: "isrc",
    0x2e: "copyright",
    0x34: "itunes_store_flavor",
    0x3B: "purchaser_email",
    0x3C: "purchaser_name",
    0x3F: "`group`",
}

def should_same(actual, expected, message: str):
    if actual != expected:
        raise Exception(f"{message} (expected: {expected}, actual: {actual})")
def should_one_of_them(actual, expected_patterns: list, message: str):
    for expected in expected_patterns:
        if actual == expected:
            return
    raise Exception(f"{message} (expected: {expected_patterns}, actual: {actual})")

def unpack_reader(format: str, reader: BytesIO):
    return unpack(format, reader.read(calcsize(format)))

def get_content():
    with open(sys.argv[1], "rb") as lf:
        first_fourcc = lf.read(4)
        should_same(first_fourcc, FOURCC, "FourCC is wrong")
        header_size, = unpack("<I", lf.read(4))
        header_size -= 8 # fourcc + int32 = 8 bytes
        header = lf.read(header_size)

        file_size, = unpack("<I", header[0:4])
        print(file_size)
        encrypted_size, = unpack("<I", header[76:80])
        print(encrypted_size)

        data_size = file_size - (header_size + 8)
        encrypted_size = data_size - (data_size % 16) if encrypted_size > file_size else encrypted_size

        encrypted = b""
        lf.seek(header_size + 8)
        raw = lf.read()
        if encrypted_size > 0:
            encrypted = lf.read(encrypted_size)
            encrypted = AES.new(b"BHUILuilfghuila3", AES.MODE_ECB).decrypt(raw[:encrypted_size])
        raw = BytesIO(zlib.decompress(encrypted + raw[encrypted_size:]))
        return raw

if os.path.exists("library.sqlite3"):
    os.remove("library.sqlite3")
db = sqlite3.connect("library.sqlite3")
db.execute("PRAGMA foreign_keys=true")
db.execute("""CREATE TABLE albums(
    id INTEGER PRIMARY KEY NOT NULL,
    title TEXT,
    artist TEXT,
    album_artist TEXT,
    binary BLOB NOT NULL
)""")
db.execute("CREATE TABLE albums_metadata_raw (album_id INTEGER NOT NULL, type INTEGER NOT NULL, binary BLOB NOT NULL, FOREIGN KEY (album_id) REFERENCES albums(id))")
db.execute("""CREATE TABLE artists (
    id INTEGER PRIMARY KEY NOT NULL,
    name TEXT,
    name_for_sort TEXT,
    binary BLOB NOT NULL
)""")
db.execute("CREATE TABLE artists_metadata_raw (artist_id INTEGER NOT NULL, type INTEGER NOT NULL, binary BLOB NOT NULL, FOREIGN KEY (artist_id) REFERENCES artists(id))")
db.execute("""CREATE TABLE tracks (
    id INTEGER PRIMARY KEY NOT NULL,
    title TEXT,
    album TEXT,
    artist TEXT,
    album_artist TEXT,
    composer TEXT,
    genre TEXT,
    comment TEXT,
    description TEXT,
    `group` TEXT,
    localized_file_type TEXT,
    copyright TEXT,
    isrc TEXT,
    title_for_sort TEXT,
    album_for_sort TEXT,
    artist_for_sort TEXT,
    album_artist_for_sort TEXT,
    composer_for_sort TEXT,
    itunes_store_flavor TEXT,
    purchaser_email TEXT,
    purchaser_name TEXT,
    binary BLOB NOT NULL
)""")
db.execute("CREATE TABLE tracks_metadata_raw (track_id INTEGER NOT NULL, type INTEGER NOT NULL, binary BLOB NOT NULL, FOREIGN KEY (track_id) REFERENCES tracks(id))")

content = get_content()

def read_chunk():
    prefix = 8
    fourcc = content.read(4)
    if fourcc == b"":
        return None
    chunk_len, = unpack("<I", content.read(4))
    if fourcc == b"boma":
        prefix += 4
        should_same(chunk_len, 20, "boma chunk first four bytes are wrong")
        chunk_len, = unpack("<I", content.read(4))
    c = content.read(chunk_len - prefix)
    # print(fourcc, chunk_len, c)
    return fourcc, c

unk3_dic = {}

def read_utf16_boma(b: BytesIO, subtype: int):
    unk1, unk2, slen, unk3, unk4 = unpack_reader("<IIIII", b)
    s = cc.read(slen).decode("utf-16")
    should_same(unk1, 0, "unk1")
    should_same(unk2, 1, "unk2")
    # should_one_of_them(unk3, [0, 1, 2, 3, 4, 5, 6], "unk3")
    if unk3 != 0:
        if subtype not in unk3_dic:
            unk3_dic[subtype] = {}
        if unk3 in unk3_dic[subtype]:
            if s != unk3_dic[subtype][unk3]:
                print("UNK3 Invalid", subtype, unk3, s, unk3_dic[subtype][unk3])
        else:
            unk3_dic[subtype][unk3] = s
    should_same(unk4, 0, "unk4")
    return s

boma_counts = 0
while content.readable():
    r = read_chunk()
    if r is None:
        break
    fourcc, bc = r
    c = BytesIO(bc)
    if fourcc == b"iama":
        c.read(4)
        boma_counts, album_id = unpack("<Iq", c.read(4 + 8))
        db.execute("INSERT INTO albums(id, binary) VALUES (?,?)", [album_id, bc])
        for i in range(boma_counts):
            fcc, cbc = read_chunk()
            cc = BytesIO(cbc)
            subtype, = unpack_reader("<I", cc)
            should_same(fcc, b"boma", "not boma")
            db.execute("INSERT INTO albums_metadata_raw (album_id, type, binary) VALUES (?,?,?)", [album_id, subtype, cbc])
            column_name = UTF16_COLUMNS_ALBUM.get(subtype)
            if column_name is not None:
                value = read_utf16_boma(cc, subtype)
                if column_name == "title":
                    print("ALBUM:TITLE", value)
                db.execute(f"UPDATE albums SET {column_name}=? WHERE id=?", [value, album_id])
            else:
                # try:
                print("WARN:ALBUM:UNHANDLED_BOMA", subtype, hex(subtype), read_utf16_boma(cc, subtype))
                # except:
                    # print("cant", subtype, hex(subtype), cbc)
    elif fourcc == b"iAma":
        c.read(4)
        boma_counts, artist_id = unpack("<Iq", c.read(4 + 8))
        db.execute("INSERT INTO artists(id, binary) VALUES (?,?)", [artist_id, bc])
        for i in range(boma_counts):
            fcc, cbc = read_chunk()
            cc = BytesIO(cbc)
            subtype, = unpack_reader("<I", cc)
            should_same(fcc, b"boma", "not boma")
            db.execute("INSERT INTO artists_metadata_raw (artist_id, type, binary) VALUES (?,?,?)", [artist_id, subtype, cbc])
            column_name = UTF16_COLUMNS_ARTIST.get(subtype)
            if column_name is not None:
                value = read_utf16_boma(cc, subtype)
                if column_name == "title":
                    print("ALBUM:TITLE", value)
                db.execute(f"UPDATE artists SET {column_name}=? WHERE id=?", [value, artist_id])
            else:
                try:
                    print("WARN:ARTIST:UNHANDLED_BOMA", subtype, hex(subtype), read_utf16_boma(cc, subtype))
                except:
                    print("WARN:ARTIST:UNHANDLED_BOMA_BINARY", subtype, hex(subtype), cbc)
    elif fourcc == b"itma":
        c.read(4) # ?
        boma_counts, track_id = unpack("<Iq", c.read(4 + 8))
        db.execute("INSERT INTO tracks(id, binary) VALUES (?,?)", [track_id, bc])
        for i in range(boma_counts):
            fcc, cbc = read_chunk()
            cc = BytesIO(cbc)
            subtype, = unpack_reader("<I", cc)
            should_same(fcc, b"boma", "not boma")
            db.execute("INSERT INTO tracks_metadata_raw (track_id, type, binary) VALUES (?,?,?)", [track_id, subtype, cbc])
            column_name = UTF16_COLUMNS_TRACK.get(subtype)
            if column_name is not None:
                value = read_utf16_boma(cc, subtype)
                if column_name == "title":
                    print("TRACK:TITLE", value)
                db.execute(f"UPDATE tracks SET {column_name}=? WHERE id=?", [value, track_id])
            else:
                try:
                    print("WARN:TRACK:UNHANDLED_BOMA:UTF-16", subtype, hex(subtype), read_utf16_boma(cc, subtype))
                except:
                    # pass
                    if subtype == 0x36:
                        print("WARN:TRACK:UNHANDLED_BOMA:BINARY", subtype, hex(subtype), cbc)
        # should_same(c.read(4), b"\xF3\x0C\x00\x00", ":(")
    else:
        print(f"skip chunk {fourcc}...")
with open("dump.sql", "w") as f:
    for line in db.iterdump():
        f.write(line)
        f.write("\n")
with open("unk3.json", "w") as f:
    json.dump(unk3_dic, f, ensure_ascii=False, indent=4)
db.commit()
db.close()