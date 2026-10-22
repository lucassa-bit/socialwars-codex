"""Raízes do site e do emulador (só para regenerar dados/imagens)."""
import os

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME_ROOT = os.environ.get("SW_ROOT") or os.path.abspath(os.path.join(SITE_ROOT, "..", "socialwarriors"))
SE_ROOT = os.environ.get("SE_ROOT") or os.path.abspath(os.path.join(SITE_ROOT, "..", "socialemperors"))

DATA_JSON = os.path.join(SITE_ROOT, "data", "units.json")
EMPIRES_JSON = os.path.join(SITE_ROOT, "data", "empires", "units.json")
SE_CONFIG_JSON = os.path.join(SE_ROOT, "config", "game_config_20120826.json")
SE_PATCH_DIR = os.path.join(SE_ROOT, "config", "patch")
BODIES_DIR = os.path.join(SITE_ROOT, "img", "bodies")
ANIM_DIR = os.path.join(SITE_ROOT, "img", "anim")
THUMBS_DIR = os.path.join(SITE_ROOT, "img", "thumbs")
WALK_DIR = os.path.join(SITE_ROOT, "img", "walk")
SE_SPRITES_DIR = os.path.join(SE_ROOT, "assets", "buildingsprites")
SE_BODIES_DIR = os.path.join(SITE_ROOT, "img", "empires", "bodies")
SE_ANIM_DIR = os.path.join(SITE_ROOT, "img", "empires", "anim")
SE_THUMBS_DIR = os.path.join(SITE_ROOT, "img", "empires", "thumbs")
SE_WALK_DIR = os.path.join(SITE_ROOT, "img", "empires", "walk")

CONFIG_JSON = os.path.join(GAME_ROOT, "config", "main.json")
PATCH_JSON = os.path.join(GAME_ROOT, "config", "patch", "unit_patch.json")
SPRITES_DIR = os.path.join(GAME_ROOT, "assets", "sprites")

FFDEC_JAR = os.environ.get("FFDEC_JAR") or os.path.join(GAME_ROOT, "tools", "_vendor", "ffdec", "ffdec.jar")
if not os.path.isfile(FFDEC_JAR):
    FFDEC_JAR = os.path.join(SITE_ROOT, "_vendor", "ffdec", "ffdec.jar")

VENDOR_DIR = os.path.join(SITE_ROOT, "_vendor")
RAW_DIR = os.path.join(VENDOR_DIR, "ffdec_raw")
SWF_BATCH = os.path.join(VENDOR_DIR, "swf_units")
