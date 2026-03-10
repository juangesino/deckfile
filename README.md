<p align="center">
  <strong>deckfile</strong>
</p>

<p align="center">
  Generate high-quality charts from YAML.<br>
  Define data sources, transformations, and chart specs in a single <code>deckfile.yaml</code>, then run <code>deck build</code>.
</p>

<p align="center">
  <a href="#installation">Installation</a> &middot;
  <a href="#quick-start">Quick Start</a> &middot;
  <a href="#cli-reference">CLI Reference</a> &middot;
  <a href="#configuration">Configuration</a> &middot;
  <a href="#chart-types">Chart Types</a> &middot;
  <a href="#python-api">Python API</a>
</p>

---

## Overview

**deckfile** is a dbt-inspired tool for chart generation. Instead of writing Python scripts for every chart, you declare what you want in YAML and let deckfile handle the rendering.

- **YAML-first**: one config file defines all your charts
- **SQL transforms**: reshape data with DuckDB queries, reference upstream sources with `ref()`
- **Multiple data sources**: local CSV files, remote URLs, Google Sheets, and derived SQL views
- **Automatic dependency resolution**: sources that depend on other sources are resolved via topological sort
- **Publication-ready output**: high-DPI PNGs with customizable themes, branding, and annotations
- **Fluent Python API**: use the same rendering engine programmatically when you need more control

## Installation

```bash
pip install deckfile
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install deckfile
```

**Python 3.11+** is required.

### Optional extras

| Extra     | Install                           | What it adds                   |
| --------- | --------------------------------- | ------------------------------ |
| `svg`     | `pip install "deckfile[svg]"`     | SVG logo support via CairoSVG  |
| `gsheets` | `pip install "deckfile[gsheets]"` | Google Sheets as a data source |
| `all`     | `pip install "deckfile[all]"`     | Everything above               |

### SVG logo support (macOS)

If you use SVG logos and see `no library called "cairo-2" was found`, install the system-level Cairo library:

```bash
brew install cairo
```

On Apple Silicon Macs, you may also need:

```bash
export DYLD_LIBRARY_PATH=/opt/homebrew/lib
```

Add that line to your `~/.zshrc` to make it permanent.

## Quick Start

### Scaffold a new project

```bash
deck init my-project
cd my-project
```

This creates:

```
my-project/
  deckfile.yaml          # chart definitions
  data/
    sample.csv           # sample data
  output/                # generated charts go here
  assets/                # logos, images
  .env.example
  .gitignore
```

### Build charts

```bash
deck build               # build all charts
deck build -s my_chart   # build a specific chart
deck list                # list all defined charts
```

### Minimal deckfile.yaml

```yaml
defaults:
  output_dir: "./output"
  theme:
    brand: "#3a58ed"

sources:
  revenue:
    type: file
    path: "data/revenue.csv"

charts:
  monthly_revenue:
    title: "Monthly Revenue"
    subtitle: "Jan - Jun 2025"
    source: revenue
    type: bar
    columns:
      x: "month"
      y: "revenue"
    x_labels:
      mode: column
      column: "month"
    y_format:
      style: "$K"
      step: 10
```

```bash
deck build
```

## CLI Reference

```
deck init [directory]                  Scaffold a new deckfile project
deck build [config] [-s CHART ...]     Build charts (default config: deckfile.yaml)
deck list [config]                     List all defined charts
deck ls [config]                       Alias for list
```

| Flag                               | Description                          |
| ---------------------------------- | ------------------------------------ |
| `-s`, `--select CHART [CHART ...]` | Build only the specified chart(s)    |
| `--debug`                          | Show full Python traceback on errors |

**Examples:**

```bash
deck init                         # scaffold in current directory
deck init my-charts               # scaffold in ./my-charts/
deck build                        # build all charts from deckfile.yaml
deck build custom.yaml            # use a different config file
deck build -s chart_a -s chart_b  # build specific charts
deck list                         # list all charts with type and title
```

## Configuration

A `deckfile.yaml` has three top-level sections:

```yaml
defaults: # Global settings (theme, branding, output, figsize)
sources: # Named data sources
charts: # Chart definitions
```

### Defaults

```yaml
defaults:
  output_dir: "./output" # where to save charts
  figsize: [16, 8.5] # default [width, height] in inches
  theme:
    brand: "#3a58ed" # any theme parameter (see Theme section)
    title_size: 24.0
  branding:
    logo:
      path: "assets/logo.png"
      zoom: 0.18
    footer:
      text: "Company Inc. · Confidential"
```

### Sources

Four source types are available:

#### File: local CSV

```yaml
sources:
  revenue:
    type: file
    path: "data/revenue.csv"
```

#### URL: remote CSV

```yaml
sources:
  metrics:
    type: url
    path: "https://example.com/data.csv"
    timeout: 30 # optional, in seconds (default: 30)
```

#### Google Sheets

Requires the `gsheets` extra and service account credentials via environment variables.

```yaml
sources:
  pipeline:
    type: gsheet
    url: "https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit"
    range: "'Sheet Name'!A2:D" # optional: sheet name, cell range, or both
    timeout: 60
```

Required environment variables (set in `.env`):

```bash
GOOGLE_AUTH_PRIVATE_KEY_ID=...
GOOGLE_AUTH_PRIVATE_KEY=...
GOOGLE_AUTH_EMAIL=...
GOOGLE_AUTH_CLIENT_ID=...
```

#### Dependent: SQL transformation over other sources

Use DuckDB SQL to join, aggregate, or reshape data from other sources. Reference upstream sources with `ref()`.

```yaml
sources:
  raw_data:
    type: file
    path: "data/raw.csv"

  quarterly:
    type: dep
    query: |
      SELECT date_trunc('quarter', created_at) AS quarter,
             SUM(revenue) AS revenue
      FROM ref(raw_data)
      GROUP BY 1
      ORDER BY 1
```

Dependencies are resolved automatically via topological sort. Circular references are detected and rejected.

#### Inline SQL on any source

Any source type can include an optional `query` field to run SQL against the loaded data. The raw data is exposed as a table called `source`:

```yaml
sources:
  filtered:
    type: file
    path: "data/all.csv"
    query: |
      SELECT * FROM source WHERE region = 'US'
```

## Chart Types

### Bar

```yaml
type: bar
columns:
  x_date: "date_column" # or x: "category_column"
  y: "value_column"
params:
  color: "#3a58ed" # bar color (uses brand color if omitted)
  alpha: 0.7 # transparency
  width: 0.65 # bar width
  label: "Revenue" # legend label
```

### Line

```yaml
type: line
columns:
  x_date: "date_column"
  y: "value_column"
params:
  smooth: true # cubic spline interpolation (default: true)
  glow: true # glow effect around line (default: true)
  fill: false # fill area under curve
  fill_alpha: 0.07 # fill transparency
  subtle_bars: false # semi-transparent bars at data points
  color: "#3a58ed" # line color (uses palette if omitted)
  linewidth: 3.0
  linestyle: "-" # "-" solid, ":" dotted, "--" dashed, "-." dashdot
  label: "Revenue"
```

### Stacked Bar

```yaml
type: stacked_bar
columns:
  x_date: "date_column"
  layers:
    "Product A": "product_a_col"
    "Product B": "product_b_col"
    "Product C": "product_c_col"
params:
  width: 0.65
  colors:
    "Product A": "#3a58ed"
    "Product B": "#10b981"
    "Product C": "#f59e0b"
  alphas:
    "Product A": 0.85
```

### Stacked Area

```yaml
type: stacked_area
columns:
  x_date: "date_column"
  layers:
    "Segment A": "segment_a_col"
    "Segment B": "segment_b_col"
params:
  smooth: true # cubic spline smoothing (default: true)
  markers: true # show markers at data points (default: true)
  normalize: false # normalize to 100% stacked
```

### Projection

Historical data with future scenario projections:

```yaml
type: projection
columns:
  x_date: "date"
  y: "actual_revenue"
  projection_start: "2026-01-01"
  scenarios:
    "Base": "base_forecast"
    "Optimistic": "high_forecast"
    "Conservative": "low_forecast"
params:
  historical_color: "#1a1a2e"
  historical_label: "Actual"
  scenario_colors:
    "Base": "#3a58ed"
    "Optimistic": "#10b981"
    "Conservative": "#ef4444"
  scenario_styles:
    "Conservative": "dashed" # solid, dashed, dotted, dashdot
  fill_between: true # shaded fill between outer scenarios
  labels:
    "Base": "Base Case ($8M)" # custom legend labels
```

### Combo (Dual Axis)

Mix bar and line series on shared or dual y-axes:

```yaml
type: combo
columns:
  x_date: "date_column"
  series:
    Users:
      column: "users_col"
      type: line
      axis: left
      label_format: "{value:,.0f}"
    Messages:
      column: "messages_col"
      type: bar
      axis: right
      label_format: "{value_k:,.0f}k"
y_format:
  style: number
  step: 100
y_format_right:
  style: K_raw
  step: 30000
axis_labels:
  left: "USERS"
  right: "MESSAGES"
```

## Chart Properties

These properties are available on all chart types:

```yaml
chart_name:
  title: "Chart Title"
  subtitle: "Description text"
  source: source_name # reference a named source
  type: line # bar | line | stacked_bar | stacked_area | projection | combo

  columns:
    x_date: "date_column" # x-axis column (date-like)
    x: "category_column" # x-axis column (categorical)
    y: "value_column" # y-axis column

  # ── Data transforms ──
  transform:
    divide_y: 1000 # divide all y-values (e.g. to show thousands)
    date_range:
      start: "2025-01-01"
      end: "2025-12-31"
    sort: true # sort by x_date (auto-detected for ISO dates)

  # ── X-axis labels ──
  x_labels:
    mode: auto_date # auto_date | column | year_month | explicit
    column: "label_col" # for mode: column
    values: ["Q1", "Q2", "Q3"] # for mode: explicit
    fontsize: 10

  # ── Y-axis formatting ──
  y_format:
    style: "K" # see Y-Axis Formatters table
    step: 50 # major tick interval

  # ── Axis limits ──
  y_lim: { bottom: 0, top: 500 }
  x_lim: { left: 0, right: 12 }
  y_lim_right: { bottom: 0 } # for combo charts

  # ── Annotations ──
  annotations:
    endpoints:
      which: first_last # first_last | first | last | all
      format: "{value:,.0f}K" # format string with {value} or {value_k}
      halo: true # halo circle on endpoint
      offset: [0, 14] # text offset in points
      layer: "Layer Name" # target a specific layer in stacked charts
    points: # arbitrary point annotations
      - x: 5.0
        y: 100.0
        text: "Peak"
        color: "#ef4444"
        fontweight: bold
        dot: true

  # ── Separators ──
  separators:
    auto: true # auto-place at label boundaries
    trigger: "Jan" # label prefix that triggers a separator
    auto_projection: true # auto-place at projection boundary
    positions: [1.5, 5.5] # explicit x positions

  # ── Legend ──
  legend:
    loc: "upper left"
    enabled: true

  # ── Output ──
  figsize: [16, 8.5] # override default figure size
  output: "custom_filename.png" # override default output filename
  dpi: 300 # override default DPI
  transparent: false # transparent background
```

## Y-Axis Formatters

| Style      | Example Output | Notes                                |
| ---------- | -------------- | ------------------------------------ |
| `"K"`      | `1,234K`       | Values already in thousands          |
| `"M"`      | `1.2M`         | Values already in millions           |
| `"$K"`     | `$1,234K`      | Currency, thousands                  |
| `"$M"`     | `$1,234M`      | Currency, millions                   |
| `"$K_raw"` | `$1.2K`        | Auto-divides raw values by 1,000     |
| `"$M_raw"` | `$1.2M`        | Auto-divides raw values by 1,000,000 |
| `"K_raw"`  | `1.2K`         | Auto-divides raw values by 1,000     |
| `"%"`      | `45%`          | Percentage                           |
| `"number"` | `1,234`        | Comma-separated integer              |

## Theme

All visual parameters are controlled through the theme system. Override any parameter in `defaults.theme`:

```yaml
defaults:
  theme:
    brand: "#3a58ed"
    bg_color: "#ffffff"
    text_color: "#1a1a2e"
    title_size: 24.0
    bar_alpha: 0.7
    line_width: 3.0
```

<details>
<summary><strong>All theme parameters</strong></summary>

### Colors

| Parameter     | Default       | Description                |
| ------------- | ------------- | -------------------------- |
| `brand`       | `#3a58ed`     | Primary brand color        |
| `bg_color`    | `#ffffff`     | Background color           |
| `text_color`  | `#1a1a2e`     | Main text color            |
| `grid_color`  | `#e8ebf0`     | Grid line color            |
| `subtle_text` | `#7c859b`     | Muted text color           |
| `separator`   | `#dde1e8`     | Vertical separator color   |
| `palette`     | 7-color cycle | Colors for multiple series |

### Typography

| Parameter           | Default      | Description            |
| ------------------- | ------------ | ---------------------- |
| `font_family`       | `sans-serif` | Font family            |
| `title_size`        | `24.0`       | Title font size        |
| `title_weight`      | `bold`       | Title font weight      |
| `subtitle_size`     | `12.5`       | Subtitle font size     |
| `axis_label_size`   | `10.0`       | Axis label font size   |
| `tick_label_size`   | `9.5`        | Tick label font size   |
| `annotation_size`   | `10.0`       | Annotation font size   |
| `annotation_weight` | `bold`       | Annotation font weight |
| `footer_size`       | `8.5`        | Footer font size       |
| `legend_fontsize`   | `10.5`       | Legend font size       |

### Layout

| Parameter       | Default | Description                   |
| --------------- | ------- | ----------------------------- |
| `figure_width`  | `16.0`  | Figure width in inches        |
| `figure_height` | `8.5`   | Figure height in inches       |
| `dpi`           | `200`   | Output resolution             |
| `margin_left`   | `0.085` | Left margin (figure fraction) |
| `margin_right`  | `0.95`  | Right margin                  |
| `margin_top`    | `0.84`  | Top margin                    |
| `margin_bottom` | `0.10`  | Bottom margin                 |
| `pad_inches`    | `0.5`   | Padding around chart          |

### Grid

| Parameter        | Default | Description          |
| ---------------- | ------- | -------------------- |
| `grid_linewidth` | `0.7`   | Grid line width      |
| `y_grid`         | `true`  | Show horizontal grid |
| `x_grid`         | `false` | Show vertical grid   |

### Lines

| Parameter    | Default | Description        |
| ------------ | ------- | ------------------ |
| `line_width` | `3.0`   | Default line width |
| `glow_width` | `8.0`   | Glow effect width  |
| `glow_alpha` | `0.10`  | Glow transparency  |

### Bars

| Parameter          | Default | Description             |
| ------------------ | ------- | ----------------------- |
| `bar_width`        | `0.55`  | Bar width fraction      |
| `bar_alpha`        | `0.7`   | Bar transparency        |
| `subtle_bar_width` | `0.45`  | Subtle bar width        |
| `subtle_bar_alpha` | `0.12`  | Subtle bar transparency |

### Endpoints

| Parameter             | Default | Description       |
| --------------------- | ------- | ----------------- |
| `endpoint_size`       | `50.0`  | Scatter dot size  |
| `endpoint_edge_width` | `1.5`   | Dot edge width    |
| `halo_size`           | `160.0` | Halo circle size  |
| `halo_alpha`          | `0.10`  | Halo transparency |

### Fill

| Parameter    | Default | Description            |
| ------------ | ------- | ---------------------- |
| `fill_alpha` | `0.07`  | Area fill transparency |

### Separators

| Parameter             | Default | Description            |
| --------------------- | ------- | ---------------------- |
| `separator_linewidth` | `0.7`   | Separator line width   |
| `separator_alpha`     | `0.6`   | Separator transparency |

### Legend

| Parameter             | Default | Description                |
| --------------------- | ------- | -------------------------- |
| `legend_frameon`      | `true`  | Show legend frame          |
| `legend_fancybox`     | `true`  | Rounded legend frame       |
| `legend_borderpad`    | `0.9`   | Legend border padding      |
| `legend_labelspacing` | `0.65`  | Space between legend items |
| `legend_handlelength` | `2.8`   | Legend handle length       |
| `legend_linewidth`    | `0.6`   | Legend frame line width    |
| `legend_alpha`        | `0.95`  | Legend frame opacity       |

### Interpolation

| Parameter       | Default | Description              |
| --------------- | ------- | ------------------------ |
| `smooth_points` | `200`   | Points in smoothed curve |
| `spline_degree` | `3`     | Cubic spline degree      |

</details>

## Branding

Add a logo and/or footer to all charts:

```yaml
defaults:
  branding:
    logo:
      path: "assets/logo.png" # PNG or SVG (SVG requires deckfile[svg])
      zoom: 0.18 # scale factor
      position: [-0.02, 1.22] # [x, y] in axes fraction
    footer:
      text: "Company Inc. · Confidential"
      x: 0.89
      y: -0.02
      ha: right
```

## Python API

deckfile exposes a fluent Python API for programmatic chart generation:

```python
from deckfile import Chart, Theme, Branding

theme = Theme.default().replace(brand="#0d9488", title_size=28)

(
    Chart(theme=theme)
    .bar(x=[0, 1, 2, 3], y=[10, 25, 18, 30], label="Revenue")
    .x_labels(["Q1", "Q2", "Q3", "Q4"])
    .y_format("$K", step=10)
    .title("Quarterly Revenue")
    .subtitle("FY 2025")
    .save("revenue.png")
)
```

### Chart methods

| Method                                                                 | Description                                             |
| ---------------------------------------------------------------------- | ------------------------------------------------------- |
| `.bar(x, y, ...)`                                                      | Add a bar series                                        |
| `.line(x, y, ...)`                                                     | Add a line series                                       |
| `.stacked_bar(x, layers, ...)`                                         | Add a stacked bar group                                 |
| `.stacked_area(x, layers, ...)`                                        | Add a stacked area group                                |
| `.projection(x_historical, y_historical, scenarios, x_projected, ...)` | Add a projection chart                                  |
| `.combo(x, items)`                                                     | Add a combo (dual axis) chart                           |
| `.x_labels(labels)`                                                    | Set x-axis tick labels                                  |
| `.y_format(style, step=...)`                                           | Configure y-axis formatting                             |
| `.y_lim(bottom=, top=)`                                                | Set y-axis limits                                       |
| `.x_lim(left=, right=)`                                                | Set x-axis limits                                       |
| `.annotate_endpoints(...)`                                             | Annotate first/last/all data points                     |
| `.annotate_point(x, y, text, ...)`                                     | Annotate a specific point                               |
| `.separators(positions)`                                               | Add vertical separator lines                            |
| `.auto_separators(labels, trigger)`                                    | Auto-place separators at label boundaries               |
| `.legend(loc=, enabled=)`                                              | Configure legend                                        |
| `.render()`                                                            | Render and return `(fig, ax)` for further customization |
| `.save(path)`                                                          | Render and save to file                                 |
| `.show()`                                                              | Render and display interactively                        |

## Build Archives

Every `deck build` automatically archives the output to `output/.archive/<timestamp>/`, so you can always compare against previous builds.

## Dependencies

| Package       | Version | Purpose                      |
| ------------- | ------- | ---------------------------- |
| matplotlib    | >= 3.7  | Chart rendering              |
| numpy         | >= 1.24 | Numerical operations         |
| scipy         | >= 1.10 | Spline interpolation         |
| pyyaml        | >= 6.0  | YAML parsing                 |
| duckdb        | >= 1.0  | SQL query engine             |
| python-dotenv | >= 1.0  | Environment variable loading |

**Optional:**

| Package     | Version | Extra     | Purpose                     |
| ----------- | ------- | --------- | --------------------------- |
| cairosvg    | >= 2.7  | `svg`     | SVG logo rendering          |
| gspread     | >= 6.0  | `gsheets` | Google Sheets API           |
| google-auth | >= 2.0  | `gsheets` | Google service account auth |

## License

MIT
