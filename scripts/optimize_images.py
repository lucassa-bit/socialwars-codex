"""Gera thumbs e walk cycles WebP a partir dos PNG masters. Não chama FFDec."""
import os
import sys
import time

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import ANIM_DIR, BODIES_DIR, THUMBS_DIR, WALK_DIR


def use_empires() -> None:
    global ANIM_DIR, BODIES_DIR, THUMBS_DIR, WALK_DIR
    from paths import SE_ANIM_DIR, SE_BODIES_DIR, SE_THUMBS_DIR, SE_WALK_DIR
    ANIM_DIR = SE_ANIM_DIR
    BODIES_DIR = SE_BODIES_DIR
    THUMBS_DIR = SE_THUMBS_DIR
    WALK_DIR = SE_WALK_DIR

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

THUMB_MAX_SIDE = 200
WALK_MAX_HEIGHT = 512
WEBP_QUALITY = 75
WEBP_METHOD = 4  # 6 trava em RGBA grande; 4 é o suficiente para catálogo
FPS = 30
FRAME_MS = round(1000 / FPS)


def _log(message: str) -> None:
    print(message, flush=True)


def _collect_stems() -> set[str]:
    stems: set[str] = set()
    if os.path.isdir(BODIES_DIR):
        for name in os.listdir(BODIES_DIR):
            if name.lower().endswith(".png"):
                stems.add(os.path.splitext(name)[0])
    if os.path.isdir(ANIM_DIR):
        for name in os.listdir(ANIM_DIR):
            folder = os.path.join(ANIM_DIR, name)
            if os.path.isdir(folder):
                stems.add(name)
    return stems


def _anim_pngs(stem: str) -> list[str]:
    folder = os.path.join(ANIM_DIR, stem)
    if not os.path.isdir(folder):
        return []
    found = [
        os.path.join(folder, name)
        for name in os.listdir(folder)
        if name.lower().endswith(".png")
    ]
    found.sort(key=lambda path: os.path.basename(path))
    return found


def _body_png(stem: str) -> str | None:
    path = os.path.join(BODIES_DIR, f"{stem}.png")
    return path if os.path.isfile(path) else None


def _fit(image: Image.Image, max_side: int | None = None, max_height: int | None = None) -> Image.Image:
    width, height = image.size
    scale = 1.0
    if max_side:
        scale = min(scale, max_side / max(width, height))
    if max_height and height:
        scale = min(scale, max_height / height)
    if scale >= 1.0:
        return image
    return image.resize(
        (max(1, round(width * scale)), max(1, round(height * scale))),
        Image.Resampling.LANCZOS,
    )


def _normalize(frames: list[Image.Image]) -> list[Image.Image]:
    """Alinha frames trimados em canvas comum para o ciclo não pular."""
    max_w = max(frame.size[0] for frame in frames)
    max_h = max(frame.size[1] for frame in frames)
    aligned = []
    for frame in frames:
        canvas = Image.new("RGBA", (max_w, max_h), (0, 0, 0, 0))
        left = (max_w - frame.size[0]) // 2
        top = (max_h - frame.size[1]) // 2
        canvas.paste(frame, (left, top), frame)
        aligned.append(canvas)
    return aligned


def _newer_than_sources(dest: str, sources: list[str]) -> bool:
    if not os.path.isfile(dest) or not sources:
        return False
    dest_mtime = os.path.getmtime(dest)
    return all(os.path.getmtime(src) <= dest_mtime for src in sources)


def _dir_bytes(folder: str) -> int:
    total = 0
    if not os.path.isdir(folder):
        return 0
    for root, _, files in os.walk(folder):
        for name in files:
            total += os.path.getsize(os.path.join(root, name))
    return total


def _kb(path: str) -> str:
    if not os.path.isfile(path):
        return "—"
    return f"{os.path.getsize(path) / 1024:.1f} KB"


def _save_webp(image: Image.Image, dest: str, extras: list[Image.Image] | None = None) -> None:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    kwargs = {
        "format": "WEBP",
        "quality": WEBP_QUALITY,
        "method": WEBP_METHOD,
    }
    if extras:
        kwargs.update(
            save_all=True,
            append_images=extras,
            duration=FRAME_MS,
            loop=0,
        )
    image.save(dest, **kwargs)


def optimize_stem(stem: str, force: bool = False) -> dict:
    body = _body_png(stem)
    frames = _anim_pngs(stem)
    thumb_src = body or (frames[0] if frames else None)
    result = {
        "thumb": "none",
        "walk": "none",
        "frames": len(frames) if frames else (1 if body else 0),
        "error": None,
    }
    if not thumb_src:
        return result

    thumb_dest = os.path.join(THUMBS_DIR, f"{stem}.webp")
    walk_dest = os.path.join(WALK_DIR, f"{stem}.webp")

    try:
        if force or not _newer_than_sources(thumb_dest, [thumb_src]):
            image = Image.open(thumb_src).convert("RGBA")
            _save_webp(_fit(image, max_side=THUMB_MAX_SIDE), thumb_dest)
            image.close()
            result["thumb"] = "write"
        else:
            result["thumb"] = "skip"

        walk_sources = frames or ([body] if body else [])
        if walk_sources:
            if force or not _newer_than_sources(walk_dest, walk_sources):
                opened = [Image.open(path).convert("RGBA") for path in walk_sources]
                # Reduz antes do canvas comum — mechs em zoom 2 estouram RAM/tempo
                opened = [_fit(frame, max_height=WALK_MAX_HEIGHT) for frame in opened]
                if len(opened) > 1:
                    opened = _normalize(opened)
                extras = opened[1:] if len(opened) > 1 else None
                _save_webp(opened[0], walk_dest, extras)
                for frame in opened:
                    frame.close()
                result["walk"] = "write"
            else:
                result["walk"] = "skip"
    except Exception as exc:
        result["error"] = str(exc)

    result["thumb_size"] = _kb(thumb_dest)
    result["walk_size"] = _kb(walk_dest)
    return result


def _fmt_eta(elapsed: float, done: int, total: int) -> str:
    if done <= 0:
        return "?"
    remaining = elapsed / done * (total - done)
    if remaining < 60:
        return f"{remaining:.0f}s"
    return f"{remaining / 60:.1f}min"


def main() -> None:
    if "--empires" in sys.argv:
        use_empires()
    force = "--force" in sys.argv
    stems = sorted(_collect_stems())
    if not stems:
        _log(" * nenhum PNG master em img/bodies ou img/anim")
        return

    _log(
        f" * {len(stems)} stems | WebP q{WEBP_QUALITY} method={WEBP_METHOD} "
        f"| walk {FPS} fps ({FRAME_MS} ms/frame)"
        f"{' | --force' if force else ''}"
    )
    wrote_thumbs = 0
    wrote_walks = 0
    errors = 0
    started = time.perf_counter()

    for index, stem in enumerate(stems, start=1):
        _log(f" [{index:3d}/{len(stems)}] {stem} ...")
        result = optimize_stem(stem, force=force)
        elapsed = time.perf_counter() - started
        if result["thumb"] == "write":
            wrote_thumbs += 1
        if result["walk"] == "write":
            wrote_walks += 1
        if result["error"]:
            errors += 1
            _log(f"            ERRO: {result['error']}")
            continue
        _log(
            f"            thumb {result['thumb']} {result.get('thumb_size', '—')} | "
            f"walk {result['walk']} {result['frames']}f {result.get('walk_size', '—')} | "
            f"{elapsed:.0f}s | eta {_fmt_eta(elapsed, index, len(stems))}"
        )

    thumb_bytes = _dir_bytes(THUMBS_DIR)
    walk_bytes = _dir_bytes(WALK_DIR)
    elapsed = time.perf_counter() - started
    _log(f" * thumbs escritos: {wrote_thumbs}")
    _log(f" * walks escritos: {wrote_walks}")
    if errors:
        _log(f" * erros: {errors}")
    _log(f" * img/thumbs: {thumb_bytes / (1024 * 1024):.2f} MB")
    _log(f" * img/walk: {walk_bytes / (1024 * 1024):.2f} MB")
    _log(f" * total publicado: {(thumb_bytes + walk_bytes) / (1024 * 1024):.2f} MB")
    _log(f" * tempo: {elapsed / 60:.1f} min")


if __name__ == "__main__":
    main()
