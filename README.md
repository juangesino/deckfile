<p align="center">
  <strong>deckfile</strong>
</p>

<p align="center">
  Generate high-quality charts from YAML.<br>
  Declare data sources, transformations, and chart specs, then run <code>deck build</code>.
</p>

<p align="center">
  <a href="#installation">Installation</a> &middot;
  <a href="#quick-start">Quick Start</a> &middot;
  <a href="#cli-reference">CLI Reference</a> &middot;
  <a href="#project-layout">Project Layout</a> &middot;
  <a href="#composition">Composition</a> &middot;
  <a href="#chart-types">Chart Types</a> &middot;
  <a href="#python-api">Python API</a>
</p>

---

## Overview

**deckfile** is a dbt-inspired tool for chart generation. Instead of writing Python scripts for every chart, you declare what you want in YAML and let deckfile handle the rendering.

- **YAML-first**: declare charts instead of scripting them
- **SQL transforms**: reshape data with DuckDB queries, reference upstream sources with `ref()`
- **Multiple data sources**: local CSV files, remote URLs, Google Sheets, Snowflake, and derived SQL views
- **Automatic dependency resolution**: sources that depend on other sources are resolved via topological sort
- **Composable**: split charts across files, keep SQL in `.sql` models, and share config with presets, `extends`, and vars
- **Graph-aware selection**: build one chart, a tagged group, a directory, or everything downstream of a model
- **Publication-ready output**: high-DPI PNGs with customizable themes, branding, and annotations
- **Storytelling annotations**: endpoint labels, callouts, and change brackets that spell out the delta between two periods
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

| Extra       | Install                             | What it adds                   |
| ----------- | ----------------------------------- | ------------------------------ |
| `svg`       | `pip install "deckfile[svg]"`       | SVG logo support via CairoSVG  |
| `gsheets`   | `pip install "deckfile[gsheets]"`   | Google Sheets as a data source |
| `snowflake` | `pip install "deckfile[snowflake]"` | Snowflake as a data source     |
| `all`       | `pip install "deckfile[all]"`       | Everything above               |

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
  deckfile.yaml          # project settings: paths, vars, defaults, theme
  charts/
    revenue.yml          # chart and preset definitions
  models/                # SQL models (one .sql file per source)
  data/
    sample.csv           # sample data
  output/                # generated charts go here
  assets/                # logos, images
  .env.example
  .gitignore
```

`charts/` and `models/` are discovered automatically. Everything can equally
live in a single `deckfile.yaml` — see [Project Layout](#project-layout).

### Build charts

```bash
deck build               # build all charts
deck build -s my_chart   # build a specific chart
deck build -s tag:revenue # build every chart carrying a tag
deck list                # list all defined charts
deck compile             # print the fully-resolved config
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

A single file stays the right shape for a small deck. When one grows past a few
dozen charts, [Project Layout](#project-layout) and [Composition](#composition)
cover splitting it up — and `deck split` does the mechanical part for you.

## CLI Reference

```
deck init [directory]                  Scaffold a new deckfile project
deck build [config] [-s SELECTOR ...]  Build charts (default config: deckfile.yaml)
deck list [config] [-s SELECTOR ...]   List defined charts
deck ls [config]                       Alias for list
deck compile [config] [-o PATH]        Print the fully-resolved config
deck split [config] [-o DIR]           Migrate a single file into models/ + charts/
deck docs                              Print this documentation
```

| Flag                                  | Description                                     |
| ------------------------------------- | ----------------------------------------------- |
| `-s`, `--select SELECTOR [SELECTOR …]` | Limit to matching charts (see [Selecting Charts](#selecting-charts)) |
| `--var NAME=VALUE`                    | Override a project var; repeatable              |
| `-o`, `--output PATH`                 | `compile`/`split` destination                   |
| `--force`                             | `split` only: overwrite an existing split       |
| `--debug`                             | Show full Python traceback on errors            |

Without an explicit config path, `deck` searches the current directory and its
parents for `deckfile.yaml`, so commands work from anywhere inside a project.

`deck list` prints each chart's name, type, title, and tags, followed by a count
of any [abstract templates](#extends), which are defined but never rendered.

**Examples:**

```bash
deck init                              # scaffold in current directory
deck build                             # build all charts
deck build custom.yaml                 # use a different config file
deck build -s chart_a -s chart_b       # build specific charts
deck build -s 'segment_country_*'      # build a family by glob
deck build -s tag:quarterly            # build everything tagged quarterly
deck build -s live+                    # build everything downstream of a model
deck build --var as_of="Jul 2026"      # override a var for one run
deck compile -o target/manifest.yaml   # write the resolved config to a file
```

## Configuration

A `deckfile.yaml` has these top-level sections, all optional:

```yaml
defaults: # Global settings (theme, branding, output, figsize)
vars: # Values interpolated as {{ var('name') }}
sources: # Named data sources
presets: # Reusable blocks of chart config
charts: # Chart definitions

model_paths: # Where to find .sql models (default: ["models"] if present)
chart_paths: # Where to find chart .yml files (default: ["charts"] if present)
default_model_type: # Source type for .sql files without ref() (default: snowflake)
```

### Defaults

```yaml
defaults:
  output_dir: "./output" # where to save charts (default: "./output")
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

A relative `output_dir` is resolved **relative to the deckfile**, not to your
current directory, so `deck build path/to/deckfile.yaml` writes to the same
place wherever you run it from. Absolute paths and `~` are used as given.

Each build clears previously rendered charts from `output_dir` before writing.
Only image files it could have produced (`.png`, `.jpg`, `.svg`, `.pdf`, …) are
removed — subdirectories, dotfiles, and anything else in the folder are left
alone, and `.archive/` is preserved. Sources are loaded *before* anything is
deleted, so a build that fails on a bad source leaves the previous charts in
place. Pointing `output_dir` at a directory containing `.git`, at your home
directory, or at the filesystem root is refused outright.

### Sources

Five source types are available:

#### File: local CSV

```yaml
sources:
  revenue:
    type: file
    path: "data/revenue.csv"
```

A relative `path` is resolved **relative to the deckfile**, matching
`output_dir`, so a project builds the same way from any working directory. If
nothing is found there, the path is tried as given, so projects that relied on
paths relative to the current directory keep working. Absolute paths and `~`
are used as given.

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

#### Snowflake

Requires the `snowflake` extra and credentials via environment variables. The `query` field is the SQL executed against the warehouse — the result becomes the source's data.

```yaml
sources:
  revenue:
    type: snowflake
    query: |
      SELECT month, mrr
      FROM analytics.revenue_monthly
      ORDER BY month

    # Optional per-source overrides (otherwise read from env):
    warehouse: COMPUTE_WH
    database: ANALYTICS
    schema: PUBLIC
    role: ANALYST
```

Required environment variables (set in `.env`):

```bash
SNOWFLAKE_ACCOUNT=myorg-myaccount
SNOWFLAKE_USER=...
```

Plus **one** of the two auth modes:

**Password auth:**

```bash
SNOWFLAKE_PASSWORD=...
```

**Key-pair auth** (preferred for production / CI). The PEM key may be stored on a single line — literal `\n` sequences are converted to real newlines at load time:

```bash
SNOWFLAKE_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBA...qv6+ys7A==\n-----END RSA PRIVATE KEY-----"
SNOWFLAKE_PRIVATE_KEY_PASSPHRASE=...   # optional, only for encrypted keys
```

If both `SNOWFLAKE_PRIVATE_KEY` and `SNOWFLAKE_PASSWORD` are set, key-pair auth wins.

Optional environment variables (used as defaults; YAML keys override):

```bash
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_DATABASE=ANALYTICS
SNOWFLAKE_SCHEMA=PUBLIC
SNOWFLAKE_ROLE=ANALYST
```

> Snowflake uppercases unquoted identifiers, so `SELECT mrr` returns a column named `MRR`. Reference that exact name in your chart's `columns:` block, or alias with quoted identifiers (`SELECT mrr AS "mrr"`) to preserve case.

Unlike other source types, the `query` field on a Snowflake source is the fetch itself, not a post-fetch DuckDB pass. To layer additional SQL on Snowflake results, use a `type: dep` source that `ref()`s the Snowflake source.

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

Any `file`, `url`, or `gsheet` source can include an optional `query` field to run DuckDB SQL against the loaded data. The raw data is exposed as a table called `source`:

```yaml
sources:
  filtered:
    type: file
    path: "data/all.csv"
    query: |
      SELECT * FROM source WHERE region = 'US'
```

> Snowflake sources are an exception: their `query` field is the SQL run against the warehouse, not a post-fetch DuckDB pass.

## Project Layout

A deckfile can be one file or many. Small projects are fine as a single
`deckfile.yaml`; past a few dozen charts, splitting pays off.

```
deckfile.yaml            project settings only
models/
  core/live.sql          a source — its name is the filename stem
  segments/country.sql
charts/
  segments/country.yml   charts:, presets:, and sources: blocks
  quarterly/growth.yml
```

Every `*.yml` under the chart paths and every `*.sql` under the model paths is
discovered recursively and merged into **one shared namespace**. Names must be
unique across the whole project — a collision is an error naming both files,
never a silent last-one-wins.

Chart files may define `charts:`, `presets:`, and `sources:`. Project-level
settings (`defaults`, `vars`, paths) belong in `deckfile.yaml`; putting them in
a chart file is an error.

Nothing here is required. A project with no `models/` or `charts/` directory
behaves exactly as it did before. To opt out explicitly, set `chart_paths: []`.

### SQL models

A `.sql` file under `models/` becomes a source named after the file:

```sql
-- models/live_monthly.sql
-- Live revenue by month, one row per account.
select date_trunc('month', d) as month, sum(mrr) as mrr
from accounts
group by 1
```

```sql
-- models/growth.sql
select * from ref(live_monthly) order by month
```

The type is inferred from the SQL: a query containing `ref()` is a `dep` model
composed from other sources; anything else uses `default_model_type`
(`snowflake` by default). To override, or to attach connection settings, add a
`sources:` entry with the same name:

```yaml
sources:
  live_monthly:
    warehouse: "BIG_WH"
    role: "ANALYST"
```

The `.sql` file supplies the query and the YAML entry supplies everything else.
Defining `query` in both places is an error.

Only the models a build actually needs are executed, so `deck build -s one_chart`
in a project with fifty models runs just that chart's upstream chain.

## Composition

Charts repeat each other far more than they differ. Three mechanisms let the
shared parts be written once.

### Presets

A preset is a named block of chart config that any chart can pull in:

```yaml
presets:
  monthly_timeseries:
    x_labels:
      mode: auto_date
    separators:
      auto: true
      trigger: "Jan"
    transform:
      sort: true

charts:
  monthly_revenue:
    preset: monthly_timeseries
    title: "Monthly Revenue"
    source: live_monthly
    type: bar
```

`preset:` takes one name or a list; later presets win over earlier ones, and
the chart's own keys win over all of them. Presets may themselves use
`extends:` to build on other presets.

### Extends

`extends:` inherits another chart's entire spec, so a variant states only what
differs:

```yaml
charts:
  # An abstract chart is a template. It is never rendered and never listed,
  # but it can be extended.
  _segment_bar:
    abstract: true
    type: bar
    annotations:
      endpoints:
        which: all

  segment_country_revenue:
    extends: _segment_bar
    title: "Revenue by Country"
    source: country_segmentation
    columns:
      y: LIVE_RUNRATE
    y_format:
      style: "$K"
      step: 200

  # Same chart, shown as a percentage.
  segment_country_revenue_pct:
    extends: segment_country_revenue
    title: "Revenue Share by Country"
    y_format:
      style: "pct"
```

Resolution order, later winning:

1. the fully-resolved chart named by `extends`
2. the chart's `preset` blocks, in order
3. the chart's own keys

### Merge rules

| Case                | Behaviour                                             |
| ------------------- | ----------------------------------------------------- |
| Nested mappings     | Merge recursively — override `y_format.step` alone     |
| Lists               | Replace wholesale (palettes, positions)                |
| `tags`              | Union, so a preset and a chart can each contribute     |
| Explicit `null`     | Deletes the inherited key                              |

To drop something a parent set:

```yaml
charts:
  unbounded:
    extends: capped_chart
    y_lim: null # remove the inherited limit
```

Inheritance cycles are detected and reported with the full chain.

### Vars

Values that repeat across many charts — a reporting period, a cutoff date —
belong in `vars:`:

```yaml
vars:
  as_of: "Jun 2026"
  period: "Q1 2024 - Q2 2026"
  cutoff: "2024-01-01"
```

```yaml
charts:
  quarterly_revenue:
    subtitle: "Live revenue run-rate · {{ var('period') }}"
```

```sql
-- models/live_monthly.sql
select * from accounts where d >= '{{ var('cutoff') }}'
```

Vars interpolate into chart specs, presets, and model SQL. A reference with no
matching var is an error; give a fallback with `{{ var('name', 'default') }}`.
Override for a single run with `--var name=value`.

A string that is *entirely* one reference keeps the var's type, so
`top: "{{ var('cap') }}"` with `cap: 1000` yields the number. Single-brace
format strings like `'{value:,.0f}'` are left untouched.

## Selecting Charts

`-s` accepts these forms, on both `build` and `list`. Multiple selectors union,
and one that matches nothing is an error.

| Selector                | Matches                                             |
| ----------------------- | --------------------------------------------------- |
| `monthly_revenue`       | One chart by name                                    |
| `segment_country_*`     | Every chart matching the glob                        |
| `tag:segments`          | Every chart carrying that tag                        |
| `path:charts/segments`  | Every chart defined in that file or directory        |
| `live+`                 | Every chart downstream of that model, through `ref()` |

Tag charts with `tags:`, which accumulates through `extends` and presets:

```yaml
charts:
  quarterly_revenue:
    tags: [quarterly, revenue]
```

`live+` walks the `ref()` graph: after editing `models/live.sql`, it rebuilds
exactly the charts that depend on it, directly or transitively.

For `path:`, the extension is optional — `path:charts/quarterly` matches both
a `quarterly/` directory and a `quarterly.yml` file.

## Inspecting and Migrating

### deck compile

`deck compile` prints the fully-resolved project — discovery, SQL models,
presets, `extends`, and vars all applied — which is exactly what the renderer
sees. Use it to check what a merge actually produced:

```bash
deck compile                          # print to stdout
deck compile -o target/manifest.yaml  # write to a file
```

### deck split

`deck split` migrates a single-file deckfile into the multi-file layout:

```bash
deck split
```

It writes each source query to `models/<name>.sql` (moving any `description`
into a header comment), groups charts into `charts/<prefix>.yml` files by name
prefix — subdividing a group that grows past a dozen charts — and reduces
`deckfile.yaml` to project settings. The original is kept as
`deckfile.yaml.bak`.

It deliberately does **not** invent presets or `extends` relationships; deciding
which charts are variants of which is a judgement call. Run it first, then
factor by hand with the duplication now visible file by file.

YAML structural comments are not carried across, since the file is re-emitted
from parsed data. Comments inside SQL survive. Verify with `deck compile` and
`deck build` afterwards.

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
  corner_radius: 0.35 # round the top corners (0 = square, 1 = semicircular cap)
```

`corner_radius` is a fraction of the bar's half-width: `0` (the default) keeps
square tops, `1` makes the radius equal to half the bar width (a semicircular
cap when the bar is tall enough). Corners stay visually circular regardless of
the chart's aspect ratio. Set the default for every chart with the
`bar_corner_radius` theme option.

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
  corner_radius: 0.35 # round the top of each stack (0 = square)
  normalize: false # normalize to 100% stacked
  colors:
    "Product A": "#3a58ed"
    "Product B": "#10b981"
    "Product C": "#f59e0b"
  alphas:
    "Product A": 0.85
```

`corner_radius` rounds the top corners of the whole stack (only the silhouette,
not every layer boundary), so the stack reads as a single bar. See the
[Bar](#bar) section for the value's meaning.

`normalize: true` rescales every column so its layers sum to 100, turning the
chart into a share-of-total view. Values land on a 0–100 scale, so pair it with
`y_format: "%"` (and optionally `y_lim: [0, 100]`). Columns whose layers all sum
to zero stay empty rather than blowing up.

By default `annotations.endpoints` labels the column **totals**, which on a
normalized stack is just `100` in every column. Point it at one band with
`layer:` to label that band's own value, drawn centered inside the band:

```yaml
annotations:
  endpoints:
    which: all
    format: "{value:.0f}%"
    layer: "Product A"
```

A `layer:` that doesn't match any layer in the group annotates nothing (rather
than silently falling back to the totals).

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

`annotations.endpoints` labels the top of the stack by default; `layer:` moves
the dot and label onto that layer's boundary line and labels the cumulative
value there (a boundary is a cumulative position, unlike a stacked *bar* band,
where `layer:` labels the band's own value).

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
    "Conservative": "dashed" # any name from the Line styles table
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

  # ── Composition (see the Composition section) ──
  extends: other_chart # inherit another chart's full spec
  preset: monthly_timeseries # apply preset block(s); one name or a list
  abstract: true # a template: never rendered, only extended
  tags: [quarterly, revenue] # for `deck build -s tag:quarterly`

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
    groups: # optional second label tier (see Grouped X-Axis Labels)
      mode: column # column | year | explicit
      column: "year"

  # ── Y-axis formatting ──
  y_format:
    style: "K" # see Y-Axis Formatters table
    step: 50 # major tick interval
    hidden: false # true hides the tick numbers (ticks and grid lines stay)

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
    change: # period-over-period delta bracket (see Change Brackets)
      from: 0 # index, x position, or x-axis label
      to: -1 # negative counts back from the end
      format: "{percent:+.0f}%"

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

`y_format.hidden: true` hides the y-axis tick numbers entirely — useful when the
shape of the chart is the message and the absolute values are noise (or
confidential). Ticks, grid lines, `step` and `y_lim` all still apply, so the
chart is laid out exactly as it would be with labels. `style` becomes optional
when `hidden` is set. `y_format_right.hidden` does the same for the right axis
of a combo chart.

## Grouped X-Axis Labels

`x_labels.groups` adds a second tier under the tick labels: a label spanning
each run of ticks, with a horizontal rule bracketing it. It turns a repetitive
axis (`Q1 '24  Q2 '24  Q3 '24 …`) into a two-level one — bare `Q1 Q2 Q3 Q4`
ticks with the year carried underneath:

```
   Q1     Q2     Q3     Q4        Q1     Q2     Q3     Q4
 ─────────────────────────────  ─────────────────────────────
             2024                           2025
```

```yaml
x_labels:
  mode: column
  column: "quarter_label" # "Q1", "Q2", …
  groups:
    column: "year" # consecutive equal values become one group
```

Runs are collapsed automatically: four rows of `2024` followed by four rows of
`2025` produce two groups, in that order. A blank value drops that tick out of
the tier entirely, so a partial year at the edge can be left unlabeled.

### Sources for the groups

| Mode       | Where the group value comes from                                    |
| ---------- | ------------------------------------------------------------------- |
| `column`   | A column in the data, one value per row (the default when `column` is set) |
| `year`     | The year of `columns.x_date` — no extra column needed                |
| `explicit` | A literal list in `values`, one entry per row                        |

`explicit` also accepts spans instead of per-row values, when the grouping
doesn't follow the data: `values: [["2024", 0, 3], ["2025", 4, 7]]`, where the
numbers are tick indices (inclusive).

### Styling

Every key below is optional and falls back to the theme.

```yaml
groups:
  column: "year"
  fontsize: 12
  color: "#1a1a2e"
  weight: bold
  rule: true # false drops the rule and keeps the label
  rule_color: "#dde1e8"
  rule_linewidth: 0.9
  rule_alpha: 1.0
  inset: 0.15 # trim each end of the rule, in tick bands
  pad: 10 # points from the tick labels down to the rule
  gap: 7 # points from the rule down to the label
```

The tier is positioned by measuring the rendered tick labels, so a two-line
label (`Jan\n'25` from `mode: auto_date`) pushes it down on its own. Raise
`pad` to open the gap further; `inset` controls how much air separates one
group's rule from the next.

Groups compose with `separators` — a vertical separator at each year boundary
plus a labeled band underneath — though either alone usually reads cleaner.

From the Python API, the same tier is one call:

```python
chart.x_labels(["Q1", "Q2", "Q3", "Q4", "Q1", "Q2"])
chart.x_groups(["2025", "2025", "2025", "2025", "2026", "2026"])
# …or with explicit spans:
chart.x_groups([("2025", 0, 3), ("2026", 4, 5)], rule=False)
```

## Change Brackets

A change bracket calls out the move between two periods — the "we cut this by
75%" callout on an otherwise ordinary chart. It draws a horizontal guide at each
value, a double-headed arrow spanning them, and a boxed label with the change:

```yaml
annotations:
  change:
    from: 0 # first bar
    to: -1 # last bar
```

That's the whole minimal form. The values are read from the chart's data, the
percent change is computed, and the arrow is placed clear of the bars — the
x-axis widens to make room for it.

`from` and `to` accept three things:

| Value      | Meaning                                        |
| ---------- | ---------------------------------------------- |
| `0`, `3`   | An x position (index, for CSV-ordered data)    |
| `-1`, `-2` | Counted back from the end — `-1` is the last   |
| `"Q1 '25"` | An x-axis label, matched against `x_labels`    |

Positions that fall between data points are interpolated, so `to: 2.5` is valid
on a line chart.

### Every option

```yaml
annotations:
  change:
    from: 0
    to: -1

    # ── What is measured ──
    from_value: 156 # override the value read from the data
    to_value: 37 #    (both optional)
    series_index: 0 # read the Nth series (default: the first one)
    layer: "Segment A" # a stacked layer, projection scenario, or combo item

    # ── What the label says ──
    mode: percent # percent | absolute | multiple
    format: "{percent:+.0f}%" # overrides mode
    label: "-75%" # literal text, overrides everything

    # ── Where it sits ──
    at: 5.4 # explicit x for the arrow
    gap: 0.5 # or: distance past the rightmost point (default)
    label_position: 0.5 # 0 = at `from`, 1 = at `to`
    label_offset: [0, 0] # extra nudge, in points
```

Styling is a separate, much larger surface — see
[Styling a change bracket](#styling-a-change-bracket) below.

Pass a **list** to draw several brackets on one chart:

```yaml
annotations:
  change:
    - { from: 0, to: 2, at: 2.75 }
    - { from: 3, to: -1, mode: absolute, format: "{delta:+,.0f} days" }
```

### Label formats

`mode` picks a sensible default format; `format` overrides it with any of these
placeholders:

| Placeholder             | Meaning                          |
| ----------------------- | -------------------------------- |
| `{percent}`             | Percent change from `from` value |
| `{delta}`               | Absolute difference              |
| `{delta_k}`, `{delta_m}`| Difference in thousands/millions |
| `{multiple}`            | `to / from`, e.g. `2.8` for 2.8x |
| `{start}`, `{end}`      | The two raw values               |

| Mode         | Default format      | Example  |
| ------------ | ------------------- | -------- |
| `percent`    | `{percent:+,.0f}%`  | `-75%`   |
| `absolute`   | `{delta:+,.0f}`     | `+220`   |
| `multiple`   | `{multiple:,.1f}x`  | `2.8x`   |

When the starting value is zero, percent and multiple are undefined — both fall
back to the absolute delta rather than printing a meaningless number.

### Which series is measured

By default the bracket reads the chart's first series. `series_index` picks a
different one, and `layer` reaches inside a group:

- **Stacked bar** — `layer` measures that band's own value; without it, the
  column totals (always 100 on a normalized stack).
- **Stacked area** — same, the layer's own value rather than the total.
- **Combo** — `layer` names an item. If that item lives on the right axis, the
  bracket is drawn against the right axis, so it lines up with the data.
- **Projection** — `layer` names a scenario; without it, the historical line.

A `layer` that matches nothing draws nothing, the same as `annotations.endpoints`.
Passing both `from_value` and `to_value` skips the data lookup entirely, which is
how you bracket against a target line or any other value not in the series.

### Styling a change bracket

A bracket is three elements — the **guides**, the **arrow**, and the **label**
(with its box). Each is independently styleable, and each falls back through a
four-step chain, most specific first:

```
change.guide_color  →  change.color  →  theme.change_guide_color  →  theme.change_color
└─ this bracket's      └─ this            └─ every bracket's         └─ every bracket
   guides                 bracket            guides
```

So `color: "#0d9488"` turns one bracket teal, `theme.change_color` turns every
bracket in the deck teal, and `guide_color` overrides just the guides of the one
bracket you put it on. The same chain applies to `linewidth`, `linestyle`, and
`alpha`.

```yaml
annotations:
  change:
    from: 0
    to: -1

    # ── Master: applies to guides, arrow, and label at once ──
    color: "#0d9488"
    linewidth: 1.6
    linestyle: dashed
    alpha: 0.9
    zorder: 9 # the label draws one step above this

    # ── Guides: the horizontal lines at each value ──
    guides: both # true | false | from | to | both | none
    guide_color: "#94a3b8"
    guide_linewidth: 1.0
    guide_linestyle: densely_dashed
    guide_alpha: 0.6
    guide_capstyle: butt # butt | round | projecting
    guide_overhang: 0.06 # how far they run past the arrow, in x units
    guide_start_offset: 0.28 # where they start; default: the bar's half-width

    # ── Arrow: the span between the two values ──
    arrow: true
    arrow_style: double # see the arrow style table
    arrow_color: "#0d9488"
    arrow_linewidth: 1.4
    arrow_linestyle: solid
    arrow_alpha: 1.0
    arrow_scale: 20 # overall head scale
    arrow_head_width: 0.25
    arrow_head_length: 0.5

    # ── Label ──
    fontsize: 11
    fontweight: bold # normal | bold | light | 100-900
    fontstyle: italic # normal | italic | oblique
    fontfamily: "SF Pro Display"
    label_color: "#065f46"
    label_alpha: 1.0
    label_rotation: 90 # degrees
    label_ha: center # horizontal alignment against the arrow
    label_va: center # vertical alignment

    # ── Label box ──
    box: true
    box_style: round # see the box style table
    box_pad: 0.5
    box_rounding: 0.4 # corner radius (round styles) or tooth size
    box_facecolor: "#ecfdf5" # default: the chart background
    box_edgecolor: "#0d9488" # default: the label color
    box_linewidth: 1.4
    box_linestyle: solid
    box_alpha: 1.0
```

#### Line styles

Any of these names works anywhere a `*_linestyle` is accepted, as does a raw
matplotlib linestyle (`"--"`, `":"`) or a dash pattern like `[6, 3]` (6 on, 3
off) — or `[0, [6, 3]]` if you need a dash offset too.

| Name              | Pattern            |
| ----------------- | ------------------ |
| `solid`           | ────────           |
| `dashed`          | ── ── ──           |
| `dotted`          | · · · · ·          |
| `dashdot`         | ─·─·─·             |
| `loosely_dashed`  | ──   ──   ──       |
| `densely_dashed`  | ──── ────          |
| `loosely_dotted`  | ·    ·    ·        |
| `densely_dotted`  | ·········          |
| `dashdotdot`      | ──·· ──··          |
| `none`            | invisible          |

#### Arrow styles

| Name            | Looks like               |
| --------------- | ------------------------ |
| `double`        | `<->` heads at both ends |
| `start`         | `<-` head at `from` only |
| `end`           | `->` head at `to` only   |
| `double_filled` | filled heads, both ends  |
| `start_filled`  | filled head at `from`    |
| `end_filled`    | filled head at `to`      |
| `bar`           | `|-|` flat caps, no head |
| `line`          | a plain line, no heads   |

Raw matplotlib arrowstyles work too, including pre-parameterized ones like
`"->,head_width=0.4"` — supply your own parameters and `arrow_head_width` /
`arrow_head_length` step aside. `arrow_head_width` sets the cap width on the
`bar` style, and is ignored by `line`.

> A dashed or dotted `arrow_linestyle` also dashes the arrowheads, which looks
> ragged on the `*_filled` styles. Pair dashes with the open heads (`double`,
> `start`, `end`) or with `bar`.

#### Box styles

`square` (default), `round`, `round4`, `circle`, `sawtooth`, `roundtooth`,
`larrow`, `rarrow`, `darrow`. `box_rounding` sets the corner radius on
`round`/`round4` and the tooth size on `sawtooth`/`roundtooth`.

The box's default `box_facecolor` is the chart background — that opaque fill is
what lets the label sit cleanly on top of the arrow. Set `box: false` for a
label with no box at all, in which case the arrow runs behind the text.

Every one of these has a `theme.change_*` counterpart, so a deck-wide bracket
style belongs in `defaults.theme` rather than repeated on each chart. See
[Change brackets](#change-brackets-1) in the theme reference.

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

| Parameter            | Default | Description                                     |
| -------------------- | ------- | ----------------------------------------------- |
| `bar_width`          | `0.55`  | Bar width fraction                              |
| `bar_alpha`          | `0.7`   | Bar transparency                                |
| `bar_corner_radius`  | `0.0`   | Rounded bar tops (fraction of half-width, 0–1)  |
| `subtle_bar_width`   | `0.45`  | Subtle bar width                                |
| `subtle_bar_alpha`   | `0.12`  | Subtle bar transparency                         |

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

### X-axis group labels

The second label tier under the ticks (see [Grouped X-Axis Labels](#grouped-x-axis-labels)).

| Parameter               | Default    | Description                                     |
| ----------------------- | ---------- | ----------------------------------------------- |
| `x_group_label_size`    | `None`     | Group label font size (`None` → `tick_label_size`) |
| `x_group_label_color`   | `None`     | Group label color (`None` → `subtle_text`)      |
| `x_group_label_weight`  | `"normal"` | Group label font weight                         |
| `x_group_rule_color`    | `None`     | Rule color (`None` → `separator`)               |
| `x_group_rule_linewidth`| `0.9`      | Rule line width                                 |
| `x_group_rule_alpha`    | `1.0`      | Rule transparency                               |
| `x_group_rule_inset`    | `0.15`     | Trim off each end of the rule, in tick bands    |
| `x_group_rule_pad`      | `10.0`     | Points from the tick labels down to the rule    |
| `x_group_label_gap`     | `7.0`      | Points from the rule down to the group label    |

### Change brackets

Master parameters — the guides, arrow, and label all inherit from these:

| Parameter          | Default     | Description                          |
| ------------------ | ----------- | ------------------------------------ |
| `change_color`     | `"#1a1a2e"` | Color of the whole bracket           |
| `change_linewidth` | `1.2`       | Line width of the whole bracket      |
| `change_linestyle` | `"solid"`   | Line style of the whole bracket      |
| `change_alpha`     | `1.0`       | Opacity of the whole bracket         |
| `change_zorder`    | `9.0`       | Draw order; the label sits one above |

Guides. `null` means "inherit the master parameter above":

| Parameter                | Default  | Description                                 |
| ------------------------ | -------- | ------------------------------------------- |
| `change_guide_color`     | `null`   | Guide color                                 |
| `change_guide_linewidth` | `null`   | Guide line width                            |
| `change_guide_linestyle` | `null`   | Guide line style                            |
| `change_guide_alpha`     | `null`   | Guide opacity                               |
| `change_guide_capstyle`  | `"butt"` | `butt`, `round`, or `projecting`            |
| `change_guide_overhang`  | `0.06`   | How far guides run past the arrow (x units) |

Arrow:

| Parameter                 | Default    | Description                        |
| ------------------------- | ---------- | ---------------------------------- |
| `change_arrow_color`      | `null`     | Arrow color                        |
| `change_arrow_linewidth`  | `null`     | Arrow line width                   |
| `change_arrow_linestyle`  | `null`     | Arrow line style                   |
| `change_arrow_alpha`      | `null`     | Arrow opacity                      |
| `change_arrow_style`      | `"double"` | Head style — see the table above   |
| `change_arrow_scale`      | `20.0`     | Overall head scale                 |
| `change_arrow_head_width` | `null`     | Head width (cap width on `bar`)    |
| `change_arrow_head_length`| `null`     | Head length                        |

Label:

| Parameter               | Default    | Description                       |
| ----------------------- | ---------- | --------------------------------- |
| `change_label_size`     | `11.0`     | Font size                         |
| `change_label_weight`   | `"bold"`   | Font weight                       |
| `change_label_style`    | `"normal"` | `normal`, `italic`, or `oblique`  |
| `change_label_family`   | `null`     | Font family                       |
| `change_label_color`    | `null`     | Label color                       |
| `change_label_alpha`    | `null`     | Label opacity                     |
| `change_label_rotation` | `0.0`      | Rotation in degrees               |

Label box:

| Parameter               | Default    | Description                            |
| ----------------------- | ---------- | -------------------------------------- |
| `change_box_style`      | `"square"` | Box shape — see the table above        |
| `change_box_pad`        | `0.5`      | Padding inside the box                 |
| `change_box_rounding`   | `null`     | Corner radius, or tooth size           |
| `change_box_facecolor`  | `null`     | Box fill; `null` → the chart background |
| `change_box_edgecolor`  | `null`     | Box border; `null` → the label color   |
| `change_box_linewidth`  | `null`     | Box border width                       |
| `change_box_linestyle`  | `null`     | Box border style                       |
| `change_box_alpha`      | `null`     | Box opacity                            |

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
| `.x_groups(groups, ...)`                                               | Add a second label tier spanning runs of ticks          |
| `.y_format(style, step=..., hidden=...)`                               | Configure y-axis formatting                             |
| `.y_lim(bottom=, top=)`                                                | Set y-axis limits                                       |
| `.x_lim(left=, right=)`                                                | Set x-axis limits                                       |
| `.annotate_endpoints(...)`                                             | Annotate first/last/all data points                     |
| `.annotate_point(x, y, text, ...)`                                     | Annotate a specific point                               |
| `.annotate_change(from_x, to_x, ...)`                                  | Bracket the change between two x positions              |
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

| Package                     | Version | Extra       | Purpose                     |
| --------------------------- | ------- | ----------- | --------------------------- |
| cairosvg                    | >= 2.7  | `svg`       | SVG logo rendering          |
| gspread                     | >= 6.0  | `gsheets`   | Google Sheets API           |
| google-auth                 | >= 2.0  | `gsheets`   | Google service account auth |
| snowflake-connector-python  | >= 3.0  | `snowflake` | Snowflake warehouse driver  |

## License

MIT
