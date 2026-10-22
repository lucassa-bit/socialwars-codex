# Social Codex

Site estático com as tropas de Social Wars e Social Empires: ficha, stats e ciclo de caminhada de frente.

Os emuladores continuam em `../socialwarriors` e `../socialemperors`. Este projeto **não** serve SWF, Ruffle nem o cliente Flash.

## Rodar local

```powershell
python scripts/serve.py
```

Abre `http://127.0.0.1:8765/`. O JSON não carrega em `file://`.

- `/` — hub (escolhe o jogo)
- `/wars.html` — tropas de Social Wars (`#/unit/1007` abre a ficha)
- `/fusion.html` — Atom Fusion (`#/mix/1062/1075` dois pais)
- `/empires.html` — tropas de Social Empires (`#/unit/516` abre a ficha)
- `/empires-fusion.html` — Soul Mixer (`#/mix/516/2037` dois pais)

## GitHub Pages

Site estático na raiz. `.nojekyll` impede o Jekyll de mexer nos arquivos. O workflow `.github/workflows/pages.yml` publica `main`.

PNG masters (`img/bodies`, `img/anim`, `img/empires/bodies`, `img/empires/anim`) ficam fora do git. O Pages serve só os WebP.

Repo precisa ser **público** no plano grátis do GitHub.

## Imagens (Wars)

O site publicado serve só `img/thumbs/` e `img/walk/` (WebP). Os PNG masters em `img/bodies/` e `img/anim/` (~680 MB) são locais, gitignored, e não vão para o ar.

```powershell
$env:SW_ROOT = "D:\socialwarriors"
python scripts/export_images.py
python scripts/optimize_images.py
python scripts/build_data.py
```

Se os PNG já existem, pule o export e rode só optimize + build. O optimize imprime cada tropa (n/total, skip/write, eta). Walk em WebP animado a 30 fps. `--force` refaz thumbs e walks.

Se alguma thumb ficar de costas: `python scripts/export_images.py --fix-facing` (pacote de 5 direções + nome `frente` no SWF) e depois optimize + build.

`SW_ROOT` aponta para o clone do emulador (`config/main.json` + `assets/sprites`). O FFDec fica em `SW_ROOT/tools/_vendor/ffdec/ffdec.jar`.

## Imagens (Empires)

SWF em `SE_ROOT/assets/buildingsprites`. PNG masters em `img/empires/bodies` e `img/empires/anim` (gitignored). O site serve `img/empires/thumbs` e `img/empires/walk`.

```powershell
$env:SE_ROOT = "D:\socialemperors"
python scripts/export_images.py --empires
python scripts/optimize_images.py --empires
python scripts/build_empires.py
```

`SE_ROOT` aponta para o clone do emulador (`config/game_config_20120826.json` + `config/patch`).
