#!/usr/bin/env python3
"""Find the three main reflected wavelengths in each measurement file and plot them vs strain.

The files in this repository use:
- tab-separated columns
- commas as decimal separators
- the first column as wavelength in nm

By default, the script extracts peaks from the OSA files. For this dataset, the three FBG
peaks that match the paired CWL files are stored in the second signal column after the
wavelength column, so ``--signal-column`` defaults to ``2``. If your instrument labels
channels differently, adjust that flag when running the script.

If you run the script with ``--CWL``, it reads the reflected wavelengths directly from the
CWL files instead of finding local maxima in the OSA traces.

The default strain step is derived from the experiment constants:
- fiber length = 36 cm
- elongation step = 100 um per file
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from pathlib import Path


DEFAULT_SIGNAL_COLUMN = 2
DEFAULT_NUM_PEAKS = 3
DEFAULT_START_STRAIN = 0.0
DEFAULT_MIN_SEPARATION_NM = 1.0
DEFAULT_FIBER_LENGTH_CM = 38.0
DEFAULT_STEP_DISPLACEMENT_UM = 100.0
DEFAULT_STRAIN_STEP = (
    DEFAULT_STEP_DISPLACEMENT_UM / (DEFAULT_FIBER_LENGTH_CM * 10_000.0) * 1_000_000.0
)
DEFAULT_OSA_CSV_OUTPUT = Path("osa_peak_summary.csv")
DEFAULT_OSA_PLOT_OUTPUT = Path("strain_vs_reflected_wavelength.png")
DEFAULT_CWL_CSV_OUTPUT = Path("cwl_peak_summary.csv")
DEFAULT_CWL_PLOT_OUTPUT = Path("cwl_strain_vs_reflected_wavelength.png")
OSA_FILENAME_RE = re.compile(r"_OSA_(\d{8}_\d{6})\.txt$")
CWL_FILENAME_RE = re.compile(r"_CWL_(\d{8}_\d{6})\.txt$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Find the strongest reflected wavelengths in each measurement file and plot "
            "reflected wavelength versus strain."
        )
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Directory containing the OSA and CWL text files (default: %(default)s).",
    )
    parser.add_argument(
        "--CWL",
        action="store_true",
        help="Use the wavelengths stored in the CWL files instead of extracting peaks from the OSA files.",
    )
    parser.add_argument(
        "--signal-column",
        type=int,
        default=DEFAULT_SIGNAL_COLUMN,
        help=(
            "Signal column to analyze, counted after the wavelength column and starting "
            "at 1 (default: %(default)s)."
        ),
    )
    parser.add_argument(
        "--num-peaks",
        type=int,
        default=DEFAULT_NUM_PEAKS,
        help="Number of local maxima to keep per file (default: %(default)s).",
    )
    parser.add_argument(
        "--min-separation-nm",
        type=float,
        default=DEFAULT_MIN_SEPARATION_NM,
        help=(
            "Minimum wavelength separation between two selected peaks in nm "
            "(default: %(default)s)."
        ),
    )
    parser.add_argument(
        "--start-strain",
        type=float,
        default=DEFAULT_START_STRAIN,
        help="Strain assigned to the first OSA file in microstrain (default: %(default)s).",
    )
    parser.add_argument(
        "--strain-step",
        type=float,
        default=DEFAULT_STRAIN_STEP,
        help="Strain increment between consecutive files in microstrain (default: %(default)s).",
    )
    parser.add_argument(
        "--csv-output",
        type=Path,
        default=None,
        help=(
            "CSV file for the extracted peaks. Defaults to "
            f"{DEFAULT_OSA_CSV_OUTPUT} in OSA mode and {DEFAULT_CWL_CSV_OUTPUT} in CWL mode."
        ),
    )
    parser.add_argument(
        "--plot-output",
        type=Path,
        default=None,
        help=(
            "PNG file for the strain/wavelength plot. Defaults to "
            f"{DEFAULT_OSA_PLOT_OUTPUT} in OSA mode and {DEFAULT_CWL_PLOT_OUTPUT} in CWL mode."
        ),
    )
    return parser.parse_args()


def parse_decimal(value: str) -> float:
    return float(value.replace(",", "."))


def osa_sort_key(path: Path) -> tuple[int, str]:
    match = OSA_FILENAME_RE.search(path.name)
    if match:
        return (0, match.group(1))
    return (1, path.name)


def cwl_sort_key(path: Path) -> tuple[int, str]:
    match = CWL_FILENAME_RE.search(path.name)
    if match:
        return (0, match.group(1))
    return (1, path.name)


def find_measurement_files(data_dir: Path, use_cwl: bool) -> list[Path]:
    pattern = "*CWL*.txt" if use_cwl else "*OSA*.txt"
    sort_key = cwl_sort_key if use_cwl else osa_sort_key
    files = sorted(data_dir.glob(pattern), key=sort_key)
    if not files:
        file_type = "CWL" if use_cwl else "OSA"
        raise FileNotFoundError(f"No {file_type} files were found in {data_dir}")
    return files


def load_signal_trace(path: Path, signal_column: int) -> tuple[list[float], list[float]]:
    wavelengths: list[float] = []
    values: list[float] = []

    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue

            parts = line.split("\t")
            if len(parts) <= signal_column:
                raise ValueError(
                    f"{path} line {line_number} has {len(parts)} columns, "
                    f"but signal column {signal_column} was requested."
                )

            wavelengths.append(parse_decimal(parts[0]))
            values.append(parse_decimal(parts[signal_column]))

    if len(wavelengths) < 3:
        raise ValueError(f"{path} does not contain enough rows to detect peaks.")

    return wavelengths, values


def load_cwl_peaks(path: Path, num_peaks: int) -> list[tuple[float, float]]:
    peaks: list[tuple[float, float]] = []

    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue

            parts = line.split("\t")
            if len(parts) < 4:
                raise ValueError(
                    f"{path} line {line_number} has {len(parts)} columns, "
                    "but at least 4 columns are required in CWL mode."
                )

            wavelength = parse_decimal(parts[2])
            value = parse_decimal(parts[3])
            peaks.append((wavelength, value))

    if len(peaks) < num_peaks:
        raise ValueError(
            f"{path} only contains {len(peaks)} peaks while {num_peaks} were requested."
        )

    return sorted(peaks[:num_peaks], key=lambda peak: peak[0])


def find_top_local_maxima(
    wavelengths: list[float],
    values: list[float],
    num_peaks: int,
    min_separation_nm: float,
) -> list[tuple[float, float]]:
    candidates: list[tuple[float, float]] = []
    for index in range(1, len(values) - 1):
        if values[index] > values[index - 1] and values[index] >= values[index + 1]:
            candidates.append((wavelengths[index], values[index]))

    candidates.sort(key=lambda peak: peak[1], reverse=True)

    chosen: list[tuple[float, float]] = []
    for wavelength, value in candidates:
        if all(abs(wavelength - existing_wavelength) >= min_separation_nm for existing_wavelength, _ in chosen):
            chosen.append((wavelength, value))
        if len(chosen) == num_peaks:
            break

    if len(chosen) != num_peaks:
        raise ValueError(
            "Only found "
            f"{len(chosen)} distinct peaks while {num_peaks} were requested."
        )

    return sorted(chosen, key=lambda peak: peak[0])


def analyze_files(
    files: list[Path],
    use_cwl: bool,
    signal_column: int,
    num_peaks: int,
    min_separation_nm: float,
    start_strain: float,
    strain_step: float,
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []

    for file_index, path in enumerate(files):
        strain = start_strain + file_index * strain_step
        if use_cwl:
            peaks = load_cwl_peaks(path, num_peaks)
        else:
            wavelengths, values = load_signal_trace(path, signal_column)
            peaks = find_top_local_maxima(
                wavelengths=wavelengths,
                values=values,
                num_peaks=num_peaks,
                min_separation_nm=min_separation_nm,
            )
        results.append(
            {
                "file": path.name,
                "strain": strain,
                "peaks": peaks,
            }
        )

    return results


def write_csv(results: list[dict[str, object]], output_path: Path) -> None:
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["file", "strain_microstrain", "peak_index", "wavelength_nm", "signal_value_db"])
        for result in results:
            for peak_index, (wavelength, value) in enumerate(result["peaks"], start=1):
                writer.writerow(
                    [
                        result["file"],
                        result["strain"],
                        peak_index,
                        f"{wavelength:.6f}",
                        f"{value:.6f}",
                    ]
                )


def linear_regression(x_values: list[float], y_values: list[float]) -> tuple[float, float]:
    if len(x_values) != len(y_values):
        raise ValueError("x_values and y_values must have the same length.")
    if len(x_values) < 2:
        raise ValueError("At least two samples are required for linear regression.")

    count = float(len(x_values))
    sum_x = sum(x_values)
    sum_y = sum(y_values)
    sum_xy = sum(x * y for x, y in zip(x_values, y_values))
    sum_xx = sum(x * x for x in x_values)

    denominator = count * sum_xx - sum_x * sum_x
    if denominator == 0:
        raise ValueError("Cannot compute a slope when all strain values are identical.")

    slope = (count * sum_xy - sum_x * sum_y) / denominator
    intercept = (sum_y - slope * sum_x) / count
    return slope, intercept


def r_squared(y_values: list[float], fitted_values: list[float]) -> float:
    if len(y_values) != len(fitted_values):
        raise ValueError("y_values and fitted_values must have the same length.")
    if not y_values:
        raise ValueError("At least one sample is required to compute R^2.")

    mean_y = sum(y_values) / len(y_values)
    ss_res = sum((y - fitted) ** 2 for y, fitted in zip(y_values, fitted_values))
    ss_tot = sum((y - mean_y) ** 2 for y in y_values)

    if ss_tot == 0:
        return 1.0

    return 1.0 - ss_res / ss_tot


def plot_results(results: list[dict[str, object]], output_path: Path, use_cwl: bool) -> None:
    try:
        matplotlib_config_dir = Path(".matplotlib")
        matplotlib_config_dir.mkdir(exist_ok=True)
        os.environ.setdefault("MPLCONFIGDIR", str(matplotlib_config_dir.resolve()))
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise SystemExit(
            "matplotlib is required to create the plot. "
            "Install it, then rerun the script."
        ) from exc

    strains = [float(result["strain"]) for result in results]
    peak_series = list(zip(*[[peak[0] for peak in result["peaks"]] for result in results]))

    plt.figure(figsize=(9, 5))
    for peak_index, wavelengths in enumerate(peak_series, start=1):
        slope, intercept = linear_regression(strains, list(wavelengths))
        fitted_wavelengths = [slope * strain + intercept for strain in strains]
        slope_pm_per_microstrain = slope * 1000.0
        fit_r_squared = r_squared(list(wavelengths), fitted_wavelengths)

        plt.plot(strains, wavelengths, marker="o", linewidth=1.8, label=f"Peak {peak_index} data")
        plt.plot(
            strains,
            fitted_wavelengths,
            linestyle="--",
            linewidth=1.4,
            label=(
                f"Peak {peak_index} fit: {slope_pm_per_microstrain:.3f} pm/microstrain, "
                f"R^2={fit_r_squared:.6f}"
            ),
        )

    plt.xlabel("Strain (microstrain)")
    plt.ylabel("Reflected wavelength (nm)")
    source_name = "CWL data" if use_cwl else "OSA data"
    plt.title(f"Strain vs reflected wavelength ({source_name})")
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()


def print_summary(results: list[dict[str, object]], signal_column: int, use_cwl: bool) -> None:
    source_name = "CWL peak list" if use_cwl else "OSA trace analysis"
    print(f"Data source: {source_name}")
    if not use_cwl:
        print(f"Signal column after wavelength: {signal_column}")
    print(
        "Strain step derived from "
        f"{DEFAULT_FIBER_LENGTH_CM:.1f} cm fiber length and "
        f"{DEFAULT_STEP_DISPLACEMENT_UM:.1f} um elongation: "
        f"{DEFAULT_STRAIN_STEP:.6f} microstrain per file"
    )
    print()
    peak_count = len(results[0]["peaks"])
    peak_headers = " ".join(f"{f'peak_{index}_nm':>12}" for index in range(1, peak_count + 1))
    header = f"{'file':38} {'strain':>10} {peak_headers}"
    print(header)
    print("-" * len(header))
    for result in results:
        peak_wavelengths = [f"{peak[0]:.3f}" for peak in result["peaks"]]
        print(
            f"{result['file']:38} "
            f"{float(result['strain']):10.1f} "
            + " ".join(f"{wavelength:>12}" for wavelength in peak_wavelengths)
        )

    print()
    for peak_index in range(peak_count):
        wavelengths = [float(result["peaks"][peak_index][0]) for result in results]
        slope, intercept = linear_regression(
            [float(result["strain"]) for result in results],
            wavelengths,
        )
        fitted_wavelengths = [slope * float(result["strain"]) + intercept for result in results]
        slope_pm_per_microstrain = slope * 1000.0
        fit_r_squared = r_squared(wavelengths, fitted_wavelengths)
        print(
            f"Peak {peak_index + 1} fit: wavelength = "
            f"{slope:.6f} * strain + {intercept:.6f} nm "
            f"({slope_pm_per_microstrain:.3f} pm/microstrain, R^2={fit_r_squared:.6f})"
        )


def main() -> None:
    args = parse_args()

    if args.signal_column < 1:
        raise SystemExit("--signal-column must be at least 1.")
    if args.num_peaks < 1:
        raise SystemExit("--num-peaks must be at least 1.")
    if args.min_separation_nm <= 0:
        raise SystemExit("--min-separation-nm must be positive.")

    csv_output = args.csv_output
    if csv_output is None:
        csv_output = DEFAULT_CWL_CSV_OUTPUT if args.CWL else DEFAULT_OSA_CSV_OUTPUT

    plot_output = args.plot_output
    if plot_output is None:
        plot_output = DEFAULT_CWL_PLOT_OUTPUT if args.CWL else DEFAULT_OSA_PLOT_OUTPUT

    files = find_measurement_files(args.data_dir, args.CWL)
    results = analyze_files(
        files=files,
        use_cwl=args.CWL,
        signal_column=args.signal_column,
        num_peaks=args.num_peaks,
        min_separation_nm=args.min_separation_nm,
        start_strain=args.start_strain,
        strain_step=args.strain_step,
    )

    write_csv(results, csv_output)
    plot_results(results, plot_output, args.CWL)
    print_summary(results, args.signal_column, args.CWL)
    print()
    print(f"CSV summary written to: {csv_output}")
    print(f"Plot written to: {plot_output}")


if __name__ == "__main__":
    main()
