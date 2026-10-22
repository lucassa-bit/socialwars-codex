"""Gera data/units.json a partir do config do emulador. Não publica SWF."""
import json
import os
import re
import subprocess
import sys
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import ANIM_DIR, BODIES_DIR, CONFIG_JSON, DATA_JSON, GAME_ROOT, PATCH_JSON, SITE_ROOT, SPRITES_DIR, THUMBS_DIR, WALK_DIR

WEAPON_RE = re.compile(
    r"bazooka|gun|sniper|rifle|pistol|shotgun|mortar|cannon|axe|sword|sward|"
    r"lance|spear|knife|blade|saber|bow|archer|flamethrower|rocket|missile|"
    r"hammer|minigun|machine.?gun|turret",
    re.I,
)
ARMED_NAME_RE = re.compile(
    r"soldier|warrior|knight|paladin|marine|commando|ranger|butcher|"
    r"axeman|crusader|hunter|spy|rifleman|gunner|samurai",
    re.I,
)
WING_RE = re.compile(
    r"wing|winged|dragon|draggy|griffin|angel|bat|pegasus|wyvern|hawk|eagle",
    re.I,
)
COST_KEYS = {"g": "gold", "w": "wood", "o": "oil", "s": "steel", "c": "cash"}

TRAIT_LABELS = OrderedDict([
    ("wings", "Asas"),
    ("weapon", "Arma"),
    ("robot", "Robô"),
    ("flying", "Voador"),
    ("human", "Humano"),
    ("armored", "Blindado"),
    ("dragon", "Dragão"),
    ("air_vehicle", "Aeronave"),
    ("land_vehicle", "Veículo"),
    ("naval", "Naval"),
    ("healer", "Curandeiro"),
    ("worker", "Trabalhador"),
    ("melee", "Corpo a corpo"),
    ("ranged", "Longo alcance"),
    ("animal", "Animal"),
])

GROUP_LABELS = OrderedDict([
    ("WORKER", "Trabalhador"),
    ("MELEE", "Corpo a corpo"),
    ("SHORT_RANGE", "Curto alcance"),
    ("LONG_RANGE", "Longo alcance"),
    ("HEALER", "Curandeiro"),
    ("LAND_VEHICLE", "Veículo terrestre"),
    ("AIR_VEHICLE", "Aeronave"),
    ("WATER_VEHICLE", "Naval"),
    ("ROBOT", "Robô"),
    ("DRAGON", "Dragão"),
    ("", "Outros"),
])


def load_items() -> list:
    if not os.path.isfile(CONFIG_JSON):
        raise FileNotFoundError(
            f"Config do jogo não encontrado: {CONFIG_JSON}\nDefina SW_ROOT para o clone do emulador."
        )
    cfg = json.load(open(CONFIG_JSON, encoding="utf-8"))
    items = list(cfg["items"])

    if os.path.exists(PATCH_JSON):
        patch = json.load(open(PATCH_JSON, encoding="utf-8"))
        print(" * unit_patch lido do disco")
    else:
        try:
            raw = subprocess.check_output(
                ["git", "show", "origin/main:config/patch/unit_patch.json"],
                cwd=GAME_ROOT,
            )
            patch = json.loads(raw.decode("utf-8"))
            print(" * unit_patch lido do origin/main")
        except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            print(" * unit_patch indisponível:", exc)
            patch = []

    added = 0
    for op in patch:
        if op.get("op") == "add" and op.get("path") == "/items/-":
            items.append(op["value"])
            added += 1
    print(f" * {added} itens adicionados pelo unit_patch")
    return items


def unit_traits(item: dict) -> list[str]:
    group = (item.get("group_type") or "").strip()
    raw = item.get("properties") or ""
    try:
        props = json.loads(raw) if raw and raw != "null" else {}
    except json.JSONDecodeError:
        props = {}
    if not isinstance(props, dict):
        props = {}

    name = item.get("name") or ""
    img = item.get("img_name") or ""
    blob = f"{name} {img}"
    traits: list[str] = []

    if group == "ROBOT":
        traits.append("robot")
    if group == "DRAGON":
        traits.append("dragon")
    if group == "AIR_VEHICLE":
        traits.append("air_vehicle")
    if group == "LAND_VEHICLE":
        traits.append("land_vehicle")
    if group == "WATER_VEHICLE":
        traits.append("naval")
    if group == "HEALER" or str(props.get("healer")) == "1":
        traits.append("healer")
    if group == "WORKER" or str(props.get("worker")) == "1":
        traits.append("worker")
    if group in ("SHORT_RANGE", "MELEE"):
        traits.append("melee")
    if group == "LONG_RANGE":
        traits.append("ranged")
    if str(props.get("ft_flying")) == "1":
        traits.append("flying")
    if str(props.get("ft_armored")) == "1":
        traits.append("armored")
    if str(props.get("human")) == "1":
        traits.append("human")
    if str(props.get("animal")) == "1":
        traits.append("animal")
    if WING_RE.search(blob) or group == "DRAGON":
        traits.append("wings")
    if WEAPON_RE.search(blob) or ARMED_NAME_RE.search(blob) or group == "LONG_RANGE":
        traits.append("weapon")

    seen = set()
    ordered = []
    for key in traits:
        if key not in seen:
            seen.add(key)
            ordered.append(key)
    return ordered


def resolve_asset(img_name: str, files: set[str], suffixes: tuple[str, ...]) -> str | None:
    parts = [p.strip() for p in (img_name or "").split(",") if p.strip()]
    for part in parts:
        for suffix in suffixes:
            candidate = f"{part}{suffix}"
            if candidate in files:
                return candidate
    return None


def parse_costs(raw: str) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {COST_KEYS.get(key, key): value for key, value in parsed.items()}


def build_catalog(items: list) -> list[dict]:
    sprites = set(os.listdir(SPRITES_DIR)) if os.path.isdir(SPRITES_DIR) else set()
    seen = set()
    catalog = []

    for item in items:
        if item.get("type") != "u":
            continue
        unit_id = str(item.get("id"))
        if unit_id in seen:
            continue
        seen.add(unit_id)

        img_name = item.get("img_name") or ""
        sprite = resolve_asset(img_name, sprites, (".swf", "_m.swf"))
        group = (item.get("group_type") or "").strip()
        stem = os.path.splitext(sprite)[0] if sprite else ""
        thumb_rel = f"img/thumbs/{stem}.webp" if stem and os.path.isfile(os.path.join(THUMBS_DIR, f"{stem}.webp")) else None
        anim_rel = f"img/walk/{stem}.webp" if stem and os.path.isfile(os.path.join(WALK_DIR, f"{stem}.webp")) else None
        body_rel = f"img/bodies/{stem}.png" if stem else None
        has_body = bool(stem and os.path.isfile(os.path.join(BODIES_DIR, f"{stem}.png")))
        frames = []
        # Flipbook PNG só quando ainda não há walk WebP
        if not anim_rel:
            anim_dir = os.path.join(ANIM_DIR, stem) if stem else ""
            if anim_dir and os.path.isdir(anim_dir):
                for name in sorted(os.listdir(anim_dir)):
                    if name.lower().endswith(".png"):
                        frames.append(f"img/anim/{stem}/{name}")
        traits = unit_traits(item)
        catalog.append({
            "id": int(unit_id),
            "name": item.get("name") or f"#{unit_id}",
            "thumb": thumb_rel,
            "image": thumb_rel or (body_rel if has_body else None),
            "anim": anim_rel,
            "frames": frames,
            "group": group,
            "group_label": GROUP_LABELS.get(group, group or "Outros"),
            "traits": traits,
            "trait_labels": [TRAIT_LABELS.get(key, key) for key in traits],
            "attack": int(item.get("attack") or 0),
            "defense": int(item.get("defense") or 0),
            "life": int(item.get("life") or 0),
            "velocity": int(item.get("velocity") or 0),
            "attack_range": int(item.get("attack_range") or 0),
            "attack_interval": int(item.get("attack_interval") or 0),
            "min_level": int(item.get("min_level") or 0),
            "population": int(item.get("population") or 0),
            "best_against": item.get("best_against") or "",
            "costs": parse_costs(item.get("costs") or ""),
            "_swf": sprite,
        })

    catalog.sort(key=lambda unit: (
        list(GROUP_LABELS.keys()).index(unit["group"]) if unit["group"] in GROUP_LABELS else 99,
        unit["id"],
    ))
    return catalog


def public_units(catalog: list[dict]) -> list[dict]:
    return [{key: value for key, value in unit.items() if not key.startswith("_")} for unit in catalog]


def write_json(catalog: list[dict]) -> None:
    os.makedirs(os.path.dirname(DATA_JSON), exist_ok=True)
    with open(DATA_JSON, "w", encoding="utf-8") as handle:
        json.dump(public_units(catalog), handle, indent=2, ensure_ascii=False)


def main() -> None:
    print(f" * GAME_ROOT={GAME_ROOT}")
    print(f" * SITE_ROOT={SITE_ROOT}")
    items = load_items()
    if "--export" in sys.argv:
        from export_images import export_bodies
        export_bodies(build_catalog(items), force="--force" in sys.argv)
    catalog = build_catalog(items)
    write_json(catalog)
    missing_image = [unit for unit in catalog if not unit["image"]]
    png_image = [unit for unit in catalog if unit.get("image") and str(unit["image"]).endswith(".png")]
    png_frames = [unit for unit in catalog if unit.get("frames")]
    print(f" * {len(catalog)} tropas gravadas em {DATA_JSON}")
    print(f" * com thumb WebP: {sum(1 for unit in catalog if unit.get('thumb'))}")
    print(f" * com anim WebP: {sum(1 for unit in catalog if unit.get('anim'))}")
    print(f" * fallback image PNG: {len(png_image)}")
    print(f" * fallback frames PNG: {len(png_frames)}")
    if missing_image:
        print(f" * sem imagem: {len(missing_image)}")


if __name__ == "__main__":
    main()
