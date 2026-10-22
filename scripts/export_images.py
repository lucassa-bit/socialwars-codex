"""Exporta PNG de frente e frames a partir dos SWF do emulador."""
import os
import shutil
import struct
import subprocess
import sys
import zlib
from collections import defaultdict

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import ANIM_DIR, BODIES_DIR, FFDEC_JAR, GAME_ROOT, RAW_DIR, SPRITES_DIR, SWF_BATCH


def use_empires() -> None:
    """Redireciona a saída/leitura de sprites para o Social Empires."""
    global ANIM_DIR, BODIES_DIR, SPRITES_DIR
    from paths import SE_ANIM_DIR, SE_BODIES_DIR, SE_SPRITES_DIR
    ANIM_DIR = SE_ANIM_DIR
    BODIES_DIR = SE_BODIES_DIR
    SPRITES_DIR = SE_SPRITES_DIR

ANIM_FRAME_COUNT = 6


def _decompress_swf(path: str) -> bytearray:
    with open(path, "rb") as handle:
        data = handle.read()
    if data[:3] == b"FWS":
        return bytearray(data)
    if data[:3] == b"CWS":
        return bytearray(data[:8] + zlib.decompress(data[8:]))
    raise ValueError(f"SWF não suportado: {data[:3]!r}")


def _write_bits(bits: list[int], nbits: int, value: int) -> None:
    if value < 0:
        value += 1 << nbits
    for index in range(nbits - 1, -1, -1):
        bits.append((value >> index) & 1)


def expand_swf_stage(path: str, xmin: int = -8000, xmax: int = 19000, ymin: int = -20000, ymax: int = 14000) -> None:
    data = _decompress_swf(path)
    nbits = data[8] >> 3
    limit = 1 << (nbits - 1)
    xmin = max(xmin, -limit)
    ymin = max(ymin, -limit)
    xmax = min(xmax, limit - 1)
    ymax = min(ymax, limit - 1)

    bits: list[int] = []
    for index in range(4, -1, -1):
        bits.append((nbits >> index) & 1)
    for value in (xmin, xmax, ymin, ymax):
        _write_bits(bits, nbits, value)
    while len(bits) % 8:
        bits.append(0)

    for offset, cursor in enumerate(range(0, len(bits), 8)):
        byte = 0
        for bit in bits[cursor : cursor + 8]:
            byte = (byte << 1) | bit
        data[8 + offset] = byte

    data[0:3] = b"FWS"
    struct.pack_into("<I", data, 4, len(data))
    with open(path, "wb") as handle:
        handle.write(data)


def _iter_tags(body: bytes):
    index = 8
    nbits = body[index] >> 3
    index += (5 + nbits * 4 + 7) // 8
    index += 4
    while index + 2 <= len(body):
        code_len = struct.unpack_from("<H", body, index)[0]
        index += 2
        tag = code_len >> 6
        length = code_len & 0x3F
        if length == 0x3F:
            length = struct.unpack_from("<I", body, index)[0]
            index += 4
        payload = body[index : index + length]
        index += length
        yield tag, payload
        if tag == 0:
            break


def _sprite_ids_by_frames(path: str) -> dict[int, list[int]]:
    sprites = []
    for tag, payload in _iter_tags(_decompress_swf(path)):
        if tag == 39 and len(payload) >= 4:
            sprites.append((
                struct.unpack_from("<H", payload, 0)[0],
                struct.unpack_from("<H", payload, 2)[0],
            ))
    by_frames: dict[int, list[int]] = defaultdict(list)
    for char_id, frames in sprites:
        if frames >= 8:
            by_frames[frames].append(char_id)
    return by_frames


def _tight_pack(ids: list[int]) -> list[int]:
    """Grupo de 4–6 IDs com passo quase constante (5 direções, sem outlier)."""
    ordered = sorted(set(ids))
    best: list[int] = []
    best_key: tuple | None = None
    for count in (5, 4, 6):
        if len(ordered) < count:
            continue
        for start in range(len(ordered) - count + 1):
            window = ordered[start : start + count]
            steps = [window[index + 1] - window[index] for index in range(count - 1)]
            avg = sum(steps) / len(steps)
            if avg < 1:
                continue
            spread = max(steps) - min(steps)
            if spread > max(4, avg * 0.6):
                continue
            key = (count == 5, avg >= 4, avg, window[-1])
            if best_key is None or key > best_key:
                best = window
                best_key = key
    return best


def find_front_pack(path: str) -> tuple[list[int], int]:
    """Pacote de direções do walk + duração em frames."""
    scored = []
    for frames, ids in _sprite_ids_by_frames(path).items():
        pack = _tight_pack(ids)
        if len(pack) < 4:
            continue
        steps = [pack[index + 1] - pack[index] for index in range(len(pack) - 1)]
        avg = sum(steps) / len(steps)
        scored.append((len(pack) == 5, frames, avg >= 4, avg, pack))
    if not scored:
        return [], 0
    _five, frames, _spaced, _avg, pack = max(scored)
    return pack, frames


def _legacy_front_sprite(path: str) -> tuple[int | None, int]:
    """Seletor antigo (max do grupo). O que está gravado nos PNG atuais."""
    scored = []
    for frames, ids in _sprite_ids_by_frames(path).items():
        if len(ids) < 4:
            continue
        ordered = sorted(ids)
        steps = [ordered[i + 1] - ordered[i] for i in range(len(ordered) - 1)]
        avg_step = sum(steps) / len(steps)
        scored.append((avg_step >= 4, frames, max(ordered)))
    if not scored:
        return None, 0
    _spaced, frames, char_id = max(scored)
    return char_id, frames


def _symbol_names(path: str) -> dict[int, str]:
    names: dict[int, str] = {}
    for tag, payload in _iter_tags(_decompress_swf(path)):
        if tag != 76 or len(payload) < 2:
            continue
        count = struct.unpack_from("<H", payload, 0)[0]
        offset = 2
        for _ in range(count):
            if offset + 2 > len(payload):
                break
            char_id = struct.unpack_from("<H", payload, offset)[0]
            offset += 2
            try:
                end = payload.index(b"\x00", offset)
            except ValueError:
                break
            names[char_id] = payload[offset:end].decode("utf-8", errors="replace")
            offset = end + 1
    return names


def pick_front_id(path: str, pack: list[int]) -> int:
    """Prefere o sprite cujo nome no SWF é 'frente'; senão o maior ID do pacote."""
    names = _symbol_names(path)
    scored: list[tuple[int, int]] = []
    for char_id in pack:
        blob = names.get(char_id, "").lower()
        if "detras" in blob or "atras" in blob or "espalda" in blob:
            continue
        if "frente" in blob or "front" in blob:
            rank = 2 if ("3_4" in blob or "3/4" in blob) else 3
            scored.append((rank, char_id))
    if scored:
        return max(scored)[1]
    return pack[-1]


def find_front_sprite(path: str) -> tuple[int | None, int]:
    """Devolve (character_id, frames) do ciclo de caminhada de frente."""
    pack, frames = find_front_pack(path)
    if not pack:
        return None, 0
    return pick_front_id(path, pack), frames


def _frame_picks(total: int, wanted: int = ANIM_FRAME_COUNT) -> list[int]:
    if total <= 1:
        return [1]
    count = min(wanted, total)
    if count == 1:
        return [1]
    return [1 + round(index * (total - 1) / (count - 1)) for index in range(count)]


def _copy_swf(src: str, dest: str) -> None:
    shutil.copy2(src, dest)
    expand_swf_stage(dest)


def _trim_png(src: str, dest: str, pad: int = 10) -> None:
    image = Image.open(src).convert("RGBA")
    bbox = image.getbbox()
    if bbox:
        image = image.crop(bbox)
    width, height = image.size
    canvas = Image.new("RGBA", (width + pad * 2, height + pad * 2), (0, 0, 0, 0))
    canvas.paste(image, (pad, pad))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    canvas.save(dest, "PNG")


def _collect_pngs(folder: str) -> list[str]:
    found = []
    for root, _, files in os.walk(folder):
        for name in files:
            if name.lower().endswith(".png") and os.path.splitext(name)[0].isdigit():
                found.append(os.path.join(root, name))
    found.sort(key=lambda path: int(os.path.splitext(os.path.basename(path))[0]))
    return found


def _pngs_for_stem(raw: str, stem: str) -> list[str]:
    pngs = _collect_pngs(os.path.join(raw, f"{stem}.swf"))
    if pngs:
        return pngs
    pngs = _collect_pngs(raw)
    if not os.path.isdir(raw):
        return pngs
    for name in os.listdir(raw):
        if stem in name:
            found = _collect_pngs(os.path.join(raw, name))
            if found:
                return found
    return pngs


def _export_group(
    char_id: int,
    frames: int,
    units: list[tuple[str, str]],
    picks: list[int],
) -> dict[str, list[str]]:
    tag = f"{char_id}_{frames}_{picks[0]}_{picks[-1]}"
    batch = os.path.join(SWF_BATCH, tag)
    raw = os.path.join(RAW_DIR, tag)
    if os.path.isdir(batch):
        shutil.rmtree(batch)
    if os.path.isdir(raw):
        shutil.rmtree(raw)
    os.makedirs(batch, exist_ok=True)
    os.makedirs(raw, exist_ok=True)
    for stem, src in units:
        _copy_swf(src, os.path.join(batch, f"{stem}.swf"))
    select = ",".join(f"{char_id}:{frame}" for frame in picks)
    print(f" * FFDec chid {char_id} ×{len(units)} frames {picks}", flush=True)
    cmd = [
        "java", "-Xmx2g", "-jar", FFDEC_JAR,
        "-selectid", str(char_id),
        "-select", select,
        "-ignorebackground",
        "-zoom", "2",
        "-format", "sprite:png",
        "-export", "sprite", raw, batch,
    ]
    result = subprocess.run(cmd, cwd=GAME_ROOT)
    if result.returncode != 0:
        print(f" * FFDec falhou no grupo {char_id} ({result.returncode})", flush=True)
        return {}
    exported = {}
    for stem, _src in units:
        pngs = _pngs_for_stem(raw, stem)
        if not pngs:
            print(f" * sem PNG: {stem} chid {char_id}", flush=True)
            continue
        exported[stem] = pngs
    return exported


def _write_body_and_anim(stem: str, pngs: list[str]) -> None:
    _trim_png(pngs[0], os.path.join(BODIES_DIR, f"{stem}.png"))
    anim_folder = os.path.join(ANIM_DIR, stem)
    if os.path.isdir(anim_folder):
        shutil.rmtree(anim_folder)
    for index, png in enumerate(pngs, start=1):
        _trim_png(png, os.path.join(anim_folder, f"{index:02d}.png"))


def export_bodies(catalog: list[dict], force: bool = False, fix_facing: bool = False) -> int:
    if not os.path.isfile(FFDEC_JAR):
        print(f" * FFDec não encontrado: {FFDEC_JAR}", flush=True)
        return 0

    os.makedirs(BODIES_DIR, exist_ok=True)
    os.makedirs(ANIM_DIR, exist_ok=True)
    if os.path.isdir(SWF_BATCH):
        shutil.rmtree(SWF_BATCH)
    if os.path.isdir(RAW_DIR):
        shutil.rmtree(RAW_DIR)
    os.makedirs(SWF_BATCH, exist_ok=True)
    os.makedirs(RAW_DIR, exist_ok=True)

    groups: dict[tuple[int, int], list[tuple[str, str]]] = defaultdict(list)
    skipped = 0
    seen = set()
    for unit in catalog:
        swf_name = unit.get("_swf")
        if not swf_name or swf_name in seen:
            continue
        seen.add(swf_name)
        stem = os.path.splitext(swf_name)[0]
        src = os.path.join(SPRITES_DIR, swf_name)
        dest = os.path.join(BODIES_DIR, f"{stem}.png")
        anim_ready = os.path.isdir(os.path.join(ANIM_DIR, stem))
        if not os.path.isfile(src):
            continue
        try:
            pack, frames = find_front_pack(src)
            old_id, _old_frames = _legacy_front_sprite(src)
            pick = pick_front_id(src, pack) if pack else None
            if not pick:
                by_frames = _sprite_ids_by_frames(src)
                if by_frames:
                    frames = max(by_frames)
                    pick = max(by_frames[frames])
                    pack = [pick]
                    old_id = pick
        except ValueError:
            pack, frames, old_id, pick = [], 0, None, None
        if not pack or not pick:
            print(f" * sem pack de frente: {stem}", flush=True)
            continue
        need = (
            force
            or fix_facing
            or not os.path.isfile(dest)
            or not anim_ready
            or pick != old_id
        )
        if not need:
            skipped += 1
            continue
        print(
            f" * {stem}: pack {pack[0]}…{pack[-1]} old={old_id} pick={pick}",
            flush=True,
        )
        groups[(pick, frames)].append((stem, src))

    written = 0
    for (char_id, frames), units in groups.items():
        exported = _export_group(char_id, frames, units, _frame_picks(frames))
        for stem, pngs in exported.items():
            _write_body_and_anim(stem, pngs)
            written += 1
            print(f" * gravado {stem} chid {char_id}", flush=True)

    print(f" * {written} PNGs de frente gravados (skip {skipped})", flush=True)
    return written


if __name__ == "__main__":
    force = "--force" in sys.argv
    fix_facing = "--fix-facing" in sys.argv
    if "--empires" in sys.argv:
        use_empires()
        from build_empires import build_catalog, load_config
        catalog = build_catalog(load_config().get("items") or [])
    else:
        from build_data import build_catalog, load_items
        catalog = build_catalog(load_items())
    export_bodies(catalog, force=force, fix_facing=fix_facing)
