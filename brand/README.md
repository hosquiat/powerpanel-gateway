# Brand assets

Logo and icon assets for PowerPanel Gateway.

## Colors

| Role  | Hex       |
| ----- | --------- |
| Green | `#1eae8e` |
| Slate | `#2c4250` |

## Source files (SVG — edit these)

| File                          | What it is                                    | Used for |
| ----------------------------- | --------------------------------------------- | -------- |
| `powerpanel-mark.svg`         | Icon mark only (house + battery/bolt + plug)  | Web UI header, favicon source |
| `powerpanel-icon-square.svg`  | Mark centered on a **square** canvas          | App/favicon icon source |
| `powerpanel-logo.svg`         | Mark + **POWERPANEL GATEWAY** wordmark lockup | README hero, add-on logo |
| `powerpanel-wordmark.svg`     | Wordmark only                                 | Misc |
| `powerpanel-logo-sheet.svg`   | Original variations sheet                     | Reference only |

## Generated raster files (PNG — do not hand-edit)

| File           | Size      | Used for |
| -------------- | --------- | -------- |
| `icon.png`     | 256×256   | HA brands `icon.png`, READMEs |
| `icon@2x.png`  | 512×512   | HA brands `icon@2x.png` |
| `logo.png`     | 512×296   | README hero, HA brands `logo.png` |
| `logo@2x.png`  | 1024×592  | HA brands `logo@2x.png` |

The add-on's own `icon.png` / `logo.png` (in
`addon-repository/powerpanel_gateway/`) and the web UI's `logo.svg` / `favicon.svg`
are copies/renders of these.

## Regenerating the PNGs

`powerpanel-icon-square.svg` is generated from `powerpanel-mark.svg` (the mark
centered on a square canvas), and the PNGs are rendered with
[`cairosvg`](https://cairosvg.org/):

```bash
pip install cairosvg pillow
python - <<'PY'
import cairosvg
cairosvg.svg2png(url="brand/powerpanel-icon-square.svg", write_to="brand/icon.png",    output_width=256, output_height=256)
cairosvg.svg2png(url="brand/powerpanel-icon-square.svg", write_to="brand/icon@2x.png", output_width=512, output_height=512)
cairosvg.svg2png(url="brand/powerpanel-logo.svg",        write_to="brand/logo.png",    output_width=512)
cairosvg.svg2png(url="brand/powerpanel-logo.svg",        write_to="brand/logo@2x.png", output_width=1024)
# add-on icon/logo
cairosvg.svg2png(url="brand/powerpanel-icon-square.svg", write_to="addon-repository/powerpanel_gateway/icon.png", output_width=256, output_height=256)
cairosvg.svg2png(url="brand/powerpanel-logo.svg",        write_to="addon-repository/powerpanel_gateway/logo.png", output_width=512)
PY
```

## Home Assistant integration icon (brands repo)

Custom integrations get their tile icon/logo from the
[`home-assistant/brands`](https://github.com/home-assistant/brands) repository,
not from this repo. To make the icon appear next to the **PowerPanel Gateway**
integration in Home Assistant, submit a PR there placing these under
`custom_integrations/powerpanel_gateway/`:

- `icon.png` (256×256) ← `brand/icon.png`
- `icon@2x.png` (512×512) ← `brand/icon@2x.png`
- `logo.png` / `logo@2x.png` ← `brand/logo.png` / `brand/logo@2x.png`
