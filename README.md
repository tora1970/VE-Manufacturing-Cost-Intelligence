# VE Manufacturing Cost Intelligence (VEMCI)

Sprint 1 establishes the HPDC vertical slice with GitHub-hosted Excel masterdata, local cache, a reusable masterdata service, a cost engine, result storage and a Streamlit user interface.

## 1. Configure the repository

Edit `config/settings.yaml`:

- `github.owner`
- `github.repository`
- `github.branch`
- paths under `masterdata`

The supplied defaults assume the masterdata repository is named `VEMCI-Masterdata` and owned by `tora1970`. Change these values if the actual owner or repository name differs.

## 2. Required Excel columns

The loader accepts several column aliases. At minimum provide:

- `materials/Materials.xlsx` or `hpdc/Alloys.xlsx`: material/alloy name and material price in EUR/kg
- `regions/Regions.xlsx`: region/country and labour rate in EUR/h
- `hpdc/Machines.xlsx`: machine name/ID and machine rate in EUR/h

Recognised examples are documented in `agents/hpdc_agent.py`.

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
