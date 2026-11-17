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
