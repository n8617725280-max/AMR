"""Chhota QR code banane wala module (koi extra library nahi chahiye).
Byte mode, error-correction level M, versions 1-10 (URL ke liye kaafi)."""

_ECC = [10, 16, 26, 18, 24, 16, 18, 22, 22, 26]   # ECC codewords per block, v1..v10 (level M)
_BLK = [1, 1, 1, 2, 2, 4, 4, 4, 5, 5]             # number of blocks, v1..v10 (level M)


def _raw_modules(v):
    r = (16 * v + 128) * v + 64
    if v >= 2:
        n = v // 7 + 2
        r -= (25 * n - 10) * n - 55
        if v >= 7:
            r -= 36
    return r


def _data_cap(v):
    return _raw_modules(v) // 8 - _ECC[v - 1] * _BLK[v - 1]


def _gf_mul(x, y):
    z = 0
    for i in range(7, -1, -1):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z


def _rs_divisor(deg):
    res = [0] * (deg - 1) + [1]
    root = 1
    for _ in range(deg):
        for j in range(deg):
            res[j] = _gf_mul(res[j], root)
            if j + 1 < deg:
                res[j] ^= res[j + 1]
        root = _gf_mul(root, 2)
    return res


def _rs_rem(data, div):
    res = [0] * len(div)
    for b in data:
        f = b ^ res.pop(0)
        res.append(0)
        for i, c in enumerate(div):
            res[i] ^= _gf_mul(c, f)
    return res


def _bit(x, i):
    return (x >> i) & 1


def make_qr(text):
    data_bytes = text.encode("utf-8")
    ver = None
    for v in range(1, 11):
        cc = 8 if v < 10 else 16
        if 4 + cc + 8 * len(data_bytes) <= _data_cap(v) * 8:
            ver = v
            break
    if ver is None:
        raise ValueError("text too long for QR")
    size = ver * 4 + 17
    cc = 8 if ver < 10 else 16
    bits = [0, 1, 0, 0] + [_bit(len(data_bytes), i) for i in range(cc - 1, -1, -1)]
    for b in data_bytes:
        bits += [_bit(b, i) for i in range(7, -1, -1)]
    cap_bits = _data_cap(ver) * 8
    bits += [0] * min(4, cap_bits - len(bits))
    bits += [0] * (-len(bits) % 8)
    pad = 0xEC
    while len(bits) < cap_bits:
        bits += [_bit(pad, i) for i in range(7, -1, -1)]
        pad ^= 0xEC ^ 0x11
    data = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]

    # blocks + error correction
    nb, eb = _BLK[ver - 1], _ECC[ver - 1]
    raw = _raw_modules(ver) // 8
    nshort = nb - raw % nb
    shortlen = raw // nb
    div = _rs_divisor(eb)
    blocks, k = [], 0
    for i in range(nb):
        dl = shortlen - eb + (0 if i < nshort else 1)
        d = data[k:k + dl]
        k += dl
        ecc = _rs_rem(d, div)
        if i < nshort:
            d = d + [0]
        blocks.append(d + ecc)
    allcw = []
    for i in range(len(blocks[0])):
        for j, blk in enumerate(blocks):
            if i != shortlen - eb or j >= nshort:
                allcw.append(blk[i])

    m = [[False] * size for _ in range(size)]
    fn = [[False] * size for _ in range(size)]

    def setf(x, y, v):
        m[y][x] = bool(v)
        fn[y][x] = True

    for i in range(size):
        setf(6, i, i % 2 == 0)
        setf(i, 6, i % 2 == 0)
    for cx, cy in ((3, 3), (size - 4, 3), (3, size - 4)):
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                x, y = cx + dx, cy + dy
                if 0 <= x < size and 0 <= y < size:
                    setf(x, y, max(abs(dx), abs(dy)) not in (2, 4))
    if ver > 1:
        n = ver // 7 + 2
        step = (ver * 4 + n * 2 + 1) // (n * 2 - 2) * 2
        pos = list(reversed([size - 7 - i * step for i in range(n - 1)] + [6]))
        for i in range(n):
            for j in range(n):
                if (i == 0 and j == 0) or (i == 0 and j == n - 1) or (i == n - 1 and j == 0):
                    continue
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        setf(pos[i] + dx, pos[j] + dy, max(abs(dx), abs(dy)) != 1)

    def draw_format(mask):
        d = (0 << 3) | mask  # level M = 0
        rem = d
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        bs = ((d << 10) | rem) ^ 0x5412
        for i in range(6):
            setf(8, i, _bit(bs, i))
        setf(8, 7, _bit(bs, 6))
        setf(8, 8, _bit(bs, 7))
        setf(7, 8, _bit(bs, 8))
        for i in range(9, 15):
            setf(14 - i, 8, _bit(bs, i))
        for i in range(8):
            setf(size - 1 - i, 8, _bit(bs, i))
        for i in range(8, 15):
            setf(8, size - 15 + i, _bit(bs, i))
        setf(8, size - 8, True)

    draw_format(0)
    if ver >= 7:
        rem = ver
        for _ in range(12):
            rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
        bs = (ver << 12) | rem
        for i in range(18):
            a, b = size - 11 + i % 3, i // 3
            setf(a, b, _bit(bs, i))
            setf(b, a, _bit(bs, i))

    i = 0
    for right in range(size - 1, 0, -2):
        if right <= 6:
            right -= 1
        for vert in range(size):
            for j in range(2):
                x = right - j
                up = ((right + 1) & 2) == 0
                y = (size - 1 - vert) if up else vert
                if not fn[y][x] and i < len(allcw) * 8:
                    m[y][x] = bool(_bit(allcw[i >> 3], 7 - (i & 7)))
                    i += 1

    masks = [
        lambda x, y: (x + y) % 2 == 0, lambda x, y: y % 2 == 0, lambda x, y: x % 3 == 0,
        lambda x, y: (x + y) % 3 == 0, lambda x, y: (x // 3 + y // 2) % 2 == 0,
        lambda x, y: x * y % 2 + x * y % 3 == 0, lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0,
        lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0,
    ]

    def apply(mask):
        f = masks[mask]
        for y in range(size):
            for x in range(size):
                if not fn[y][x] and f(x, y):
                    m[y][x] = not m[y][x]

    def penalty():
        p = 0
        rows = m
        cols = [[m[y][x] for y in range(size)] for x in range(size)]
        for lines in (rows, cols):
            for ln in lines:
                run = 1
                for k in range(1, size):
                    if ln[k] == ln[k - 1]:
                        run += 1
                    else:
                        if run >= 5:
                            p += run - 2
                        run = 1
                if run >= 5:
                    p += run - 2
                s = "".join("1" if c else "0" for c in ln)
                for pat in ("00001011101", "10111010000"):
                    st = 0
                    while True:
                        st = s.find(pat, st)
                        if st < 0:
                            break
                        p += 40
                        st += 1
        for y in range(size - 1):
            for x in range(size - 1):
                if m[y][x] == m[y][x + 1] == m[y + 1][x] == m[y + 1][x + 1]:
                    p += 3
        dark = sum(c for r in m for c in r)
        p += (abs(dark * 20 - size * size * 10) // (size * size)) * 10
        return p

    best, bm = None, 0
    for mk in range(8):
        apply(mk)
        draw_format(mk)
        pn = penalty()
        if best is None or pn < best:
            best, bm = pn, mk
        apply(mk)
    apply(bm)
    draw_format(bm)
    return m


def qr_svg(text, scale=10, border=4):
    m = make_qr(text)
    n = len(m)
    d = []
    for y in range(n):
        for x in range(n):
            if m[y][x]:
                d.append("M%d,%dh1v1h-1z" % (x + border, y + border))
    dim = n + border * 2
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" shape-rendering="crispEdges">'
        '<rect width="100%%" height="100%%" fill="#fff"/><path d="%s" fill="#000"/></svg>'
        % (dim, dim, dim * scale, dim * scale, "".join(d))
    )
