"""Gera data/empires/units.json a partir do config do Social Empires. Sem imagens."""
import json
import os
import sys
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import (
    EMPIRES_JSON,
    SE_ANIM_DIR,
    SE_BODIES_DIR,
    SE_CONFIG_JSON,
    SE_PATCH_DIR,
    SE_ROOT,
    SE_SPRITES_DIR,
    SE_THUMBS_DIR,
    SE_WALK_DIR,
)

COST_KEYS = {"g": "gold", "w": "wood", "o": "oil", "s": "steel", "c": "cash", "f": "food"}

TRAIT_TOKENS = OrderedDict([
    ("dragon", ("dragon", "Dragão")),
    ("ranged", ("ranged", "Longo alcance")),
    ("melee", ("melee", "Corpo a corpo")),
    ("flying", ("flying", "Voador")),
    ("worker", ("worker", "Trabalhador")),
    ("villager", ("worker", "Trabalhador")),
    ("healer", ("healer", "Curandeiro")),
    ("cavalry", ("cavalry", "Cavalaria")),
    ("siege", ("siege", "Cerco")),
    ("small", ("small", "Pequeno")),
    ("slow", ("slow", "Lento")),
    ("fast", ("fast", "Rápido")),
])

RACE_TRAITS = {
    "h": ("human", "Humano"),
    "e": ("elf", "Elfo"),
    "d": ("dark", "Sombrio"),
}


def _unescape(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def _walk(doc, path: str):
    if not path or path == "/":
        raise ValueError("patch na raiz não suportado")
    parts = [_unescape(part) for part in path.lstrip("/").split("/")]
    cursor = doc
    for part in parts[:-1]:
        if isinstance(cursor, list):
            cursor = cursor[int(part)]
        else:
            cursor = cursor[part]
    return cursor, parts[-1]


def apply_patch(doc, ops: list) -> None:
    for op in ops:
        kind = op.get("op")
        path = op.get("path", "")
        parent, key = _walk(doc, path)
        if kind == "add":
            if isinstance(parent, list):
                if key == "-":
                    parent.append(op["value"])
                else:
                    parent.insert(int(key), op["value"])
            else:
                parent[key] = op["value"]
        elif kind == "replace":
            if isinstance(parent, list):
                parent[int(key)] = op["value"]
            else:
                parent[key] = op["value"]
        elif kind == "remove":
            if isinstance(parent, list):
                del parent[int(key)]
            else:
                del parent[key]


def load_config() -> dict:
    if not os.path.isfile(SE_CONFIG_JSON):
        raise FileNotFoundError(
            f"Config do Empires não encontrado: {SE_CONFIG_JSON}\nDefina SE_ROOT para o clone do emulador."
        )
    config = json.load(open(SE_CONFIG_JSON, encoding="utf-8"))
    if not os.path.isdir(SE_PATCH_DIR):
        return config
    applied = 0
    for name in sorted(os.listdir(SE_PATCH_DIR)):
        if not name.endswith(".json"):
            continue
        raw = json.load(open(os.path.join(SE_PATCH_DIR, name), encoding="utf-8"))
        if not isinstance(raw, list) or not raw or not isinstance(raw[0], dict) or "op" not in raw[0]:
            print(f" * patch ignorado (não é JSON Patch): {name}")
            continue
        try:
            apply_patch(config, raw)
            applied += 1
            print(f" * patch: {name}")
        except Exception as exc:
            print(f" * patch falhou {name}: {exc}")
    print(f" * {applied} patches aplicados")
    return config


def unit_traits(item: dict) -> tuple[list[str], list[str]]:
    tokens = (item.get("groups") or "").lower().split()
    keys: list[str] = []
    labels: list[str] = []
    seen = set()

    def add(key: str, label: str) -> None:
        if key in seen:
            return
        seen.add(key)
        keys.append(key)
        labels.append(label)

    if str(item.get("flying")) == "1":
        add("flying", "Voador")
    race = RACE_TRAITS.get((item.get("race") or "").lower())
    if race:
        add(*race)
    for token in tokens:
        mapped = TRAIT_TOKENS.get(token)
        if mapped:
            add(*mapped)
        elif token and token not in seen:
            add(token, token.replace("_", " ").title())
    store = (item.get("store_groups") or "").strip()
    if store and store.lower() not in seen:
        add(store.lower().replace(" ", "_"), store)
    return keys, labels


def parse_costs(item: dict) -> dict:
    raw = item.get("cost")
    kind = COST_KEYS.get(item.get("cost_type") or "", item.get("cost_type") or "")
    if raw in (None, "", "0") or not kind:
        extra = item.get("cost_unit_cash")
        if extra not in (None, "", "0"):
            return {"cash": int(extra)}
        return {}
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return {}
    if value <= 0:
        return {}
    return {kind: value}


def resolve_sprite(img_name: str, files: dict[str, str]) -> str | None:
    for part in [piece.strip() for piece in (img_name or "").split(",") if piece.strip()]:
        for suffix in (".swf", "_m.swf"):
            key = f"{part}{suffix}".lower()
            if key in files:
                return files[key]
    return None


def build_catalog(items: list) -> list[dict]:
    files = {}
    if os.path.isdir(SE_SPRITES_DIR):
        for name in os.listdir(SE_SPRITES_DIR):
            if name.lower().endswith(".swf"):
                files[name.lower()] = name
    seen = set()
    catalog = []
    for item in items:
        if item.get("type") != "u":
            continue
        unit_id = str(item.get("id") or "")
        if not unit_id or unit_id in seen:
            continue
        seen.add(unit_id)
        store = (item.get("store_groups") or "").strip()
        tokens = (item.get("groups") or "").split()
        group = store or (tokens[0] if tokens else "")
        traits, trait_labels = unit_traits(item)
        sprite = resolve_sprite(item.get("img_name") or "", files)
        stem = os.path.splitext(sprite)[0] if sprite else ""
        thumb_rel = f"img/empires/thumbs/{stem}.webp" if stem and os.path.isfile(os.path.join(SE_THUMBS_DIR, f"{stem}.webp")) else None
        anim_rel = f"img/empires/walk/{stem}.webp" if stem and os.path.isfile(os.path.join(SE_WALK_DIR, f"{stem}.webp")) else None
        body_rel = f"img/empires/bodies/{stem}.png" if stem else None
        has_body = bool(stem and os.path.isfile(os.path.join(SE_BODIES_DIR, f"{stem}.png")))
        frames = []
        if not anim_rel and stem:
            anim_dir = os.path.join(SE_ANIM_DIR, stem)
            if os.path.isdir(anim_dir):
                for name in sorted(os.listdir(anim_dir)):
                    if name.lower().endswith(".png"):
                        frames.append(f"img/empires/anim/{stem}/{name}")
        catalog.append({
            "id": int(unit_id),
            "name": item.get("name") or f"#{unit_id}",
            "thumb": thumb_rel,
            "image": thumb_rel or (body_rel if has_body else None),
            "anim": anim_rel,
            "frames": frames,
            "group": group,
            "group_label": store or (tokens[0].replace("_", " ").title() if tokens else "Outros"),
            "traits": traits,
            "trait_labels": trait_labels,
            "_swf": sprite,
            "attack": int(item.get("attack") or 0),
            "defense": int(item.get("defense") or 0),
            "life": int(item.get("life") or 0),
            "velocity": int(item.get("velocity") or 0),
            "attack_range": int(item.get("attack_range") or 0),
            "attack_interval": int(item.get("attack_interval") or 0),
            "min_level": int(item.get("min_level") or 0),
            "population": int(item.get("population") or 0),
            "best_against": item.get("best_against") or "",
            "costs": parse_costs(item),
        })
    catalog.sort(key=lambda unit: (unit["group_label"], unit["id"]))
    return catalog


def public_units(catalog: list[dict]) -> list[dict]:
    return [{key: value for key, value in unit.items() if not key.startswith("_")} for unit in catalog]


def main() -> None:
    print(f" * SE_ROOT={SE_ROOT}")
    config = load_config()
    catalog = build_catalog(config.get("items") or [])
    os.makedirs(os.path.dirname(EMPIRES_JSON), exist_ok=True)
    with open(EMPIRES_JSON, "w", encoding="utf-8") as handle:
        json.dump(public_units(catalog), handle, indent=2, ensure_ascii=False)
    with_swf = sum(1 for unit in catalog if unit.get("_swf"))
    with_thumb = sum(1 for unit in catalog if unit.get("thumb"))
    with_anim = sum(1 for unit in catalog if unit.get("anim"))
    print(f" * {len(catalog)} tropas gravadas em {EMPIRES_JSON}")
    print(f" * com SWF: {with_swf}")
    print(f" * com thumb WebP: {with_thumb}")
    print(f" * com anim WebP: {with_anim}")


if __name__ == "__main__":
    main()
