"""Pure-Python LHA (-lh0- / -lh5-) reader.

Fallback used only when the bundled tools/7za.exe is unavailable or fails.
It is enough to pull ID1/PAK0.PAK out of the Quake 1.06 shareware
``resource.1`` (an "LHA's SFX 2.13L" self-extracting archive).

Slower than 7za (pure Python), but stdlib-only and dependency-free.
The caller verifies the extracted pak0.pak MD5, so no CRC16 check is done here.
"""

import struct

# LH5 parameters
_DICBIT = 13
_MAXMATCH = 256
_THRESHOLD = 3
_NC = 255 + _MAXMATCH + 2 - _THRESHOLD   # 510 literal/length symbols
_CBIT = 9
_NT = 16 + 3                               # 19 code-length symbols
_TBIT = 5
_NP = _DICBIT + 1                          # 14 position symbols
_PBIT = 4


class LhaError(Exception):
    pass


class LhaEntry(object):
    __slots__ = ("name", "method", "data_offset", "packed_size", "original_size")

    def __init__(self, name, method, data_offset, packed_size, original_size):
        self.name = name
        self.method = method
        self.data_offset = data_offset
        self.packed_size = packed_size
        self.original_size = original_size

    def __repr__(self):
        return "LhaEntry(%r, %s, %d -> %d)" % (
            self.name, self.method, self.packed_size, self.original_size)


def _decode_name(raw):
    name = raw.replace(b"\xff", b"/").replace(b"\\", b"/")
    return name.decode("latin-1")


def _looks_like_header(data, pos):
    if pos + 22 > len(data):
        return False
    m = data[pos + 2:pos + 7]
    return (m[:3] == b"-lh" and m[4:5] == b"-") or m in (b"-lz4-", b"-lzs-", b"-lz5-")


def list_entries(data):
    """Return LhaEntry list for an LHA archive / SFX held in ``data`` (bytes)."""
    # Find first header: skip any SFX stub.
    pos = -1
    search = 0
    while True:
        i = data.find(b"-lh", search)
        if i < 0:
            raise LhaError("No LHA header found")
        cand = i - 2
        if cand >= 0 and _looks_like_header(data, cand) and data[cand + 20] in (0, 1, 2):
            pos = cand
            break
        search = i + 1

    entries = []
    n = len(data)
    while pos < n:
        if data[pos] == 0:
            break  # end-of-archive marker
        if not _looks_like_header(data, pos):
            break
        level = data[pos + 20]
        method = data[pos + 2:pos + 7].decode("ascii", "replace")
        packed, original = struct.unpack_from("<II", data, pos + 7)
        if level in (0, 1):
            hsize = data[pos]
            name_len = data[pos + 21]
            name = _decode_name(data[pos + 22:pos + 22 + name_len])
            data_off = pos + 2 + hsize
            if level == 1:
                # Extended headers follow the base header and are counted in packed size.
                ext = struct.unpack_from("<H", data, pos + hsize)[0]
                dirname = ""
                while ext:
                    etype = data[data_off]
                    body = data[data_off + 1:data_off + ext - 2]
                    if etype == 1:
                        name = _decode_name(body)
                    elif etype == 2:
                        dirname = _decode_name(body)
                    packed -= ext
                    nxt = struct.unpack_from("<H", data, data_off + ext - 2)[0]
                    data_off += ext
                    ext = nxt
                if dirname:
                    name = dirname.rstrip("/") + "/" + name
        elif level == 2:
            hsize = struct.unpack_from("<H", data, pos)[0]
            off = pos + 24
            ext = struct.unpack_from("<H", data, off)[0]
            off += 2
            name = ""
            dirname = ""
            while ext:
                etype = data[off]
                body = data[off + 1:off + ext - 2]
                if etype == 1:
                    name = _decode_name(body)
                elif etype == 2:
                    dirname = _decode_name(body)
                ext2 = struct.unpack_from("<H", data, off + ext - 2)[0]
                off += ext
                ext = ext2
            if dirname:
                name = dirname.rstrip("/") + "/" + name
            data_off = pos + hsize
        else:
            raise LhaError("Unsupported LHA header level %d" % level)
        entries.append(LhaEntry(name, method, data_off, packed, original))
        pos = data_off + packed
    return entries


def _make_table(nchar, lengths):
    """Build a full 16-bit lookup table: value = (symbol << 5) | code_length."""
    table = [0] * 65536
    count = [0] * 17
    for ln in lengths:
        if ln > 16:
            raise LhaError("Bad Huffman code length")
        count[ln] += 1
    code = 0
    start = [0] * 18
    for ln in range(1, 17):
        start[ln] = code
        code += count[ln] << (16 - ln)
    if code & 0xFFFF:
        raise LhaError("Bad Huffman table")
    for sym in range(nchar):
        ln = lengths[sym]
        if ln == 0:
            continue
        s = start[ln]
        span = 1 << (16 - ln)
        table[s:s + span] = [(sym << 5) | ln] * span
        start[ln] = s + span
    return table


def decode_lh5(src, original_size):
    """Decompress an -lh5- stream ``src`` (bytes) to ``original_size`` bytes."""
    data = src
    dlen = len(data)
    pos = 0
    bitbuf = 0
    bitcnt = 0
    out = bytearray()
    out_extend = out.extend
    out_append = out.append

    # --- bit helpers implemented as closures over mutable state lists for speed
    state = [0, 0, 0]  # pos, bitbuf, bitcnt (only used in helper funcs)

    def getbits(n):
        p, bb, bc = state
        while bc < n:
            bb = (bb << 8) | (data[p] if p < dlen else 0)
            p += 1
            bc += 8
        bc -= n
        v = (bb >> bc) & ((1 << n) - 1)
        bb &= (1 << bc) - 1
        state[0], state[1], state[2] = p, bb, bc
        return v

    def peek16():
        p, bb, bc = state
        while bc < 16:
            bb = (bb << 8) | (data[p] if p < dlen else 0)
            p += 1
            bc += 8
        state[0], state[1], state[2] = p, bb, bc
        return (bb >> (bc - 16)) & 0xFFFF

    def read_pt_len(nn, nbit, i_special):
        n = getbits(nbit)
        if n == 0:
            c = getbits(nbit)
            return None, c
        lens = [0] * nn
        i = 0
        lim = min(n, nn)
        while i < lim:
            w = peek16()
            c = w >> 13
            if c == 7:
                mask = 1 << 12
                while w & mask:
                    mask >>= 1
                    c += 1
                    if c > 16:
                        raise LhaError("Corrupt LH5 stream (pt_len)")
                getbits(c - 3)
            else:
                getbits(3)
            lens[i] = c
            i += 1
            if i == i_special:
                z = getbits(2)
                while z > 0 and i < nn:
                    lens[i] = 0
                    i += 1
                    z -= 1
        return lens, None

    def read_c_len(pt_tab, pt_single):
        n = getbits(_CBIT)
        if n == 0:
            c = getbits(_CBIT)
            return None, c
        lens = [0] * _NC
        i = 0
        while i < n:
            if pt_single is not None:
                c = pt_single
            else:
                e = pt_tab[peek16()]
                c = e >> 5
                getbits(e & 31)
            if c <= 2:
                if c == 0:
                    c = 1
                elif c == 1:
                    c = getbits(4) + 3
                else:
                    c = getbits(_CBIT) + 20
                while c > 0 and i < _NC:
                    lens[i] = 0
                    i += 1
                    c -= 1
            else:
                lens[i] = c - 2
                i += 1
        return lens, None

    while len(out) < original_size:
        blocksize = getbits(16)
        if blocksize == 0:
            blocksize = 65536
        t_lens, t_single = read_pt_len(_NT, _TBIT, 3)
        t_tab = _make_table(_NT, t_lens) if t_lens is not None else None
        c_lens, c_single = read_c_len(t_tab, t_single)
        c_tab = _make_table(_NC, c_lens) if c_lens is not None else None
        p_lens, p_single = read_pt_len(_NP, _PBIT, -1)
        p_tab = _make_table(_NP, p_lens) if p_lens is not None else None

        # Hot loop: inline bit handling with locals.
        pos, bitbuf, bitcnt = state
        remaining = original_size - len(out)
        while blocksize > 0 and remaining > 0:
            blocksize -= 1
            # decode_c
            while bitcnt < 16:
                bitbuf = (bitbuf << 8) | (data[pos] if pos < dlen else 0)
                pos += 1
                bitcnt += 8
            if c_tab is not None:
                e = c_tab[(bitbuf >> (bitcnt - 16)) & 0xFFFF]
                c = e >> 5
                bitcnt -= e & 31
                bitbuf &= (1 << bitcnt) - 1
            else:
                c = c_single
            if c < 256:
                out_append(c)
                remaining -= 1
                continue
            length = c - 256 + _THRESHOLD
            # decode_p
            while bitcnt < 16:
                bitbuf = (bitbuf << 8) | (data[pos] if pos < dlen else 0)
                pos += 1
                bitcnt += 8
            if p_tab is not None:
                e = p_tab[(bitbuf >> (bitcnt - 16)) & 0xFFFF]
                p = e >> 5
                bitcnt -= e & 31
                bitbuf &= (1 << bitcnt) - 1
            else:
                p = p_single
            if p > 1:
                nb = p - 1
                while bitcnt < nb:
                    bitbuf = (bitbuf << 8) | (data[pos] if pos < dlen else 0)
                    pos += 1
                    bitcnt += 8
                bitcnt -= nb
                p = (1 << nb) + ((bitbuf >> bitcnt) & ((1 << nb) - 1))
                bitbuf &= (1 << bitcnt) - 1
            dist = p + 1
            start = len(out) - dist
            if start < 0:
                raise LhaError("Corrupt LH5 stream (distance before start)")
            if length > remaining:
                length = remaining
            if dist >= length:
                out_extend(out[start:start + length])
            else:
                for k in range(length):
                    out_append(out[start + k])
            remaining -= length
        state[0], state[1], state[2] = pos, bitbuf, bitcnt
    return bytes(out[:original_size])


def extract_member(archive_path, member_suffix, out_path):
    """Extract the first entry whose name ends with ``member_suffix`` (case-insensitive).

    Returns the archive name of the extracted entry.
    """
    with open(archive_path, "rb") as fh:
        data = fh.read()
    want = member_suffix.replace("\\", "/").lower()
    for ent in list_entries(data):
        if ent.name.lower().endswith(want):
            raw = data[ent.data_offset:ent.data_offset + ent.packed_size]
            if ent.method == "-lh0-":
                payload = raw[:ent.original_size]
            elif ent.method == "-lh5-":
                payload = decode_lh5(raw, ent.original_size)
            else:
                raise LhaError("Unsupported LHA method %s for %s" % (ent.method, ent.name))
            with open(out_path, "wb") as oh:
                oh.write(payload)
            return ent.name
    raise LhaError("%s not found in %s" % (member_suffix, archive_path))


def extract_all(archive_path, dest_dir):
    """Extract every -lh0-/-lh5- entry into dest_dir (zip-slip safe)."""
    import os
    with open(archive_path, "rb") as fh:
        data = fh.read()
    dest_real = os.path.realpath(dest_dir)
    count = 0
    for ent in list_entries(data):
        if ent.name.endswith("/"):
            continue
        target = os.path.realpath(os.path.join(dest_real, ent.name))
        if not target.startswith(dest_real + os.sep):
            raise LhaError("Unsafe path in archive: %s" % ent.name)
        raw = data[ent.data_offset:ent.data_offset + ent.packed_size]
        if ent.method == "-lh0-":
            payload = raw[:ent.original_size]
        elif ent.method == "-lh5-":
            payload = decode_lh5(raw, ent.original_size)
        elif ent.method == "-lhd-":
            os.makedirs(target, exist_ok=True)
            continue
        else:
            raise LhaError("Unsupported LHA method %s for %s" % (ent.method, ent.name))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as oh:
            oh.write(payload)
        count += 1
    return count
