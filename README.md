# Lab FBG Sensors

Small Python project to analyze Fiber Bragg Grating measurements from Optical Spectrum Analyzer (`OSA`) and center-wavelength (`CWL`) exports.

The script:
- finds the 3 main reflected wavelengths for each measurement
- converts measurement steps into strain
- performs a linear least-squares fit for each peak
- reports the slope and `R^2`
- generates a `strain vs reflected wavelength` plot

## Repository Contents

```text
.
├── analyze_osa_strain.py
├── requirements.txt
├── data/
│   ├── *_OSA_*.txt
│   └── *_CWL_*.txt
├── osa_peak_summary.csv
├── strain_vs_reflected_wavelength.png
├── cwl_peak_summary.csv
└── cwl_strain_vs_reflected_wavelength.png
```

## Experiment Assumptions

The script uses the following default experimental constants:

- fiber length: `36 cm`
- displacement step: `100 µm` per measurement

This gives a strain step of:

```text
100 µm / 360000 µm = 2.77777778e-4
strain = 277.777778 µstrain per file
```

## Setup

Create a virtual environment and install the dependency:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Usage

### 1. Use OSA data

This is the default mode. The script reads the `OSA` files, detects the 3 strongest local maxima, then fits wavelength versus strain.

```bash
.venv/bin/python analyze_osa_strain.py
```

Default outputs in this mode:

- `osa_peak_summary.csv`
- `strain_vs_reflected_wavelength.png`

### 2. Use CWL data

If you want to use the wavelengths already exported in the `CWL` files, run with `--CWL`:

```bash
.venv/bin/python analyze_osa_strain.py --CWL
```

Default outputs in this mode:

- `cwl_peak_summary.csv`
- `cwl_strain_vs_reflected_wavelength.png`

## Outputs

You can still override the output names manually if needed:

```bash
.venv/bin/python analyze_osa_strain.py --CWL \
  --csv-output cwl_peak_summary.csv \
  --plot-output cwl_strain_vs_reflected_wavelength.png
```

The plot contains:

- measured peak wavelengths
- linear regression lines
- slope in `pm/µstrain`
- coefficient of determination `R^2`
- the data source in the title: `OSA data` or `CWL data`

## Important Notes

- The input files use tab-separated values.
- Decimal values use commas, for example `1547,201`.
- In OSA mode, the first column is wavelength in `nm`.
- For this dataset, the relevant reflected peaks are in signal column `2` after the wavelength column, so the script defaults to `--signal-column 2`.
- If your instrument stores the useful trace in another OSA signal column, change it with `--signal-column`.

Example:

```bash
.venv/bin/python analyze_osa_strain.py --signal-column 3
```

## Main Options

```bash
.venv/bin/python analyze_osa_strain.py --help
```

Useful arguments:

- `--CWL`: use `CWL` files instead of extracting peaks from `OSA` traces
- `--data-dir`: choose another data directory
- `--signal-column`: choose the OSA signal column to analyze
- `--num-peaks`: number of peaks to keep
- `--min-separation-nm`: minimum spacing between selected peaks
- `--start-strain`: strain assigned to the first file
- `--strain-step`: strain increment between files
- `--csv-output`: output CSV filename
- `--plot-output`: output plot filename

## Example Results

With the current dataset:

- OSA mode and CWL mode give very similar peak wavelengths
- fitted slopes are close to `0.97-0.98 pm/µstrain`
- `R^2` values are close to `0.999`

## License

Add a license here if you plan to make the repository public.
