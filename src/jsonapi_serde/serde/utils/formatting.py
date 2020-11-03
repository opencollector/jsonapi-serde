import typing


def english_enumerate(items: typing.Iterable[str], conj: str = ", and ") -> str:
    buf = []

    i = iter(items)
    try:
        x = next(i)
    except StopIteration:
        return ""
    buf.append(x)

    lx: typing.Optional[str] = None

    for x in i:
        if lx is not None:
            buf.append(", ")
            buf.append(lx)
        lx = x
    if lx is not None:
        buf.append(conj)
        buf.append(lx)
    return "".join(buf)
