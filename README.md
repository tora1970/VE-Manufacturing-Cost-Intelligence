# VE Manufacturing Cost Intelligence (VEMCI)

Sprint 1 establishes the HPDC vertical slice with GitHub-hosted Excel masterdata, local cache, a reusable masterdata service, a cost engine, result storage and a Streamlit user interface.

## 1. Configure the repository

Edit `config/settings.yaml`:

- `github.owner`
- `github.repository`
- `github.branch`
- paths under `masterdata`

The supplied defaults use the configured VEMCI repository and central `Masterdata/` directory. Change these values if the repository or branch differs.

## 2. Required Excel columns

The loader accepts several column aliases. At minimum provide:

- `Masterdata/Materials.xlsx`: `Material_ID`, `Material_Name`, `Material_Group`,
  `Density`, and `Default_Price_EUR_kg`
- `Masterdata/Regions.xlsx`: region/country and labour rate in EUR/h
- `Masterdata/Machine.xlsx` (configured as `masterdata.machine`):
  `Process`, `Size`, `Machine Hour Rate €/h`, `Max Part Size` (two dimensions),
  and `Max Part Weight` (kg). HPDC is mapped to the source process `Die Casting`;
  available classes are evaluated in Small, Medium, Large order.

Recognised examples are documented in `agents/hpdc_agent.py`.

The current Materials workbook does not define process compatibility or
material recovery value. HPDC therefore displays the full masterdata material
list until process compatibility is recorded (for example, in a
`Compatible_Processes` field containing `Die Casting`).

The HPDC-specific workflow is available in the **HPDC Should-cost** tab. Its
cycle-time prediction uses the transparent, configurable Engineering Estimate
V1 assumptions in `hpdc_cycle_time_v1`. The user must enter nominal wall
thickness; it is not inferred from the part bounding box, weight, or density.
V1 calculates a bounded fill-time estimate from total shot weight and an
assumed fill rate, and a wall-thickness screening cooling time. Intensification/
hold and cooling overlap, so the closed phase uses their maximum rather than
their sum. Die movement, hold, ejection, and spray/handling times are configured
assumptions, not measured machine data. The estimate is not a casting or
thermal simulation.

An optional cycle-time override is applied to all existing production and cost
calculations; the V1 prediction remains visible for comparison. Missing or
invalid V1 configuration is reported rather than falling back to the former
fixed cycle-time default. Estimated cavity layout dimensions use the
configurable `hpdc_defaults.layout_factor` (default `1.25`) and are not
validated die-design dimensions.

Trimming is modeled as an optional downstream HPDC station. If enabled and no
trim cycle is entered, VEMCI estimates it as 16.7% of the effective HPDC cycle
time; this is a default engineering assumption, not masterdata. The model
converts good parts per shot into trim cycles and required trim time per shot,
then compares that station load with the HPDC cycle to report the effective
production takt and whether trim is the bottleneck. HPDC and trim are treated
as separate stations: trim time is not added to HPDC cycle time or HPDC machine
cost. `trim_parts_per_cycle` is the number of cast parts processed
simultaneously in one complete trim-press cycle. A four-part HPDC shot trimmed
as a complete layout uses four parts per trim cycle and one trim cycle per shot;
if trimmed individually, it uses one part per trim cycle and four trim cycles
per shot. VEMCI reuses its existing `good_parts_per_shot` and
`trim_cycles_per_shot` outputs for these calculations.

Trim machine selection and rates come from `Masterdata/Machine.xlsx` rows with
`Process=Trim`. `Process + Size` identifies a Trim machine. Automatic
selection compares the part's dimensions and weight with `Max Part Size` and
`Max Part Weight`, then selects the first capable class in Small, Medium, Large
order. If the capability fields are missing, the UI allows explicit selection
from the Trim rows while still resolving the rate from masterdata.

The runtime loader fetches the configured GitHub `masterdata.machine` path
through a cache, so an existing cached workbook can remain in use until its
configured TTL expires or it is refreshed. The current refreshed runtime
workbook contains Trim / Small, Trim / Medium, and Trim / Large rows with rates
of 35, 42.5, and 65 EUR/h, respectively; the rate used is always the value in
the loaded workbook.

The resolved trim-machine rate adds a separate **Trim Machine Cost** using the
trim station's required processing time per HPDC shot. This is a machine-only
amount; direct labour, indirect overhead and supplier margin are excluded.
When no suitable Trim machine can be resolved, the calculation reports the
masterdata issue rather than substituting an engineering rate.

For example, with four good parts per shot, a 10 s trim cycle and a €30/hr
trim-machine rate, processing all four parts together takes 10 s/shot and costs
about €0.0833/shot or €0.0208/good part. Trimming the four parts individually
takes 40 s/shot and costs about €0.3333/shot or €0.0833/good part. In both
cases the HPDC cycle remains 60 s. `effective_takt_s` is a capacity/bottleneck
metric and is not used as billable trim-machine time. Scrap timing relative to
trimming is not further expanded; the model uses the existing good-parts and
trim-cycles outputs without adding scrap-stage logic.

HPDC recurring manufacturing cost is reported per good part as material,
material overhead, machine, labour, trim, and production overhead. Material
overhead defaults to 5.0% and applies only to the material cost per good part.
Material, machine, labour, and trim costs are normalized for process yield
according to the existing model; metal yield remains a separate material-weight
adjustment. Production overhead remains applied only to good-part machine and
labour costs and excludes material overhead. Tooling investment and tool life
are reported separately as project CAPEX, with gross tool life calculated as
shots multiplied by cavities.

## 3. Public or private masterdata

For a public repository, keep:

```yaml
private_repository: false
```

For a private repository:

```yaml
private_repository: true
```

Then define the token only as an environment variable, never in source control:

```bash
export VEMCI_GITHUB_TOKEN="your-token"
```

Use a fine-grained token with read-only access to the masterdata repository.

## 4. Install and run

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## 5. Test

```bash
python -m pytest -q
```

## Cost model boundary

The included model is a transparent Sprint 1 baseline. It calculates material, machine, labour, tooling amortisation, scrap, overhead, unit cost and annual cost. Validate the formulas and masterdata column mappings against the approved HPDC agent before using results for supplier negotiation or investment decisions.
