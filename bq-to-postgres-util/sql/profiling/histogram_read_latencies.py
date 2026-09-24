#!/usr/bin/env python3
# Created by Claude Code Sonnet 5
"""
Pull Cloud SQL for PostgreSQL query-latency distribution data from Cloud
Monitoring, tidy it with pandas, and plot:
  1. A histogram of latency summed across the whole window
  2. A day-by-day heatmap showing how the distribution shifts over time

Requires:
    pip install google-cloud-monitoring pandas numpy matplotlib

Auth: uses Application Default Credentials. Run:
    gcloud auth application-default login
first, or set GOOGLE_APPLICATION_CREDENTIALS to a service account key with
roles/monitoring.viewer on the project.

Usage:
    python cloudsql_read_latency_histogram.py \\
        --project my-gcp-project \\
        --instance my-instance-id \\
        --weeks 6
"""

import argparse
import time
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from google.cloud import monitoring_v3

METRIC_TYPE = "cloudsql.googleapis.com/database/postgresql/insights/perquery/latencies"

# Cloud Monitoring filter expression (RE2 regex, case-insensitive) matching
# only normalized query strings that are SELECT statements. Adjust if you
# use leading comments/tags before SELECT and want those included too.
SELECT_ONLY_FILTER = 'metric.labels.querystring = monitoring.regex.full_match("(?i)^select .*")'


def bucket_bounds_us(bucket_options) -> np.ndarray:
    """Return the lower bound (in microseconds, the metric's native unit)
    of every bucket, plus one extra edge for the final (overflow) bucket,
    for whichever bucket layout Cloud Monitoring used."""
    if bucket_options.linear_buckets.num_finite_buckets:
        b = bucket_options.linear_buckets
        n = b.num_finite_buckets
        edges = b.offset + b.width * np.arange(0, n + 2)
    elif bucket_options.exponential_buckets.num_finite_buckets:
        b = bucket_options.exponential_buckets
        n = b.num_finite_buckets
        edges = b.scale * (b.growth_factor ** np.arange(0, n + 2))
    elif bucket_options.explicit_buckets.bounds:
        edges = np.array([0.0] + list(bucket_options.explicit_buckets.bounds))
    else:
        raise ValueError("Unrecognized bucket layout")
    return edges


def fetch_daily_distributions(project_id: str, instance_id: str, weeks: int,
                               database: str | None = None) -> pd.DataFrame:
    """Return a tidy long-form DataFrame: one row per (day, bucket)."""
    client = monitoring_v3.MetricServiceClient()
    project_name = f"projects/{project_id}"

    now = datetime.now(timezone.utc)
    start = now - timedelta(weeks=weeks)
    interval = monitoring_v3.TimeInterval(
        end_time={"seconds": int(now.timestamp())},
        start_time={"seconds": int(start.timestamp())},
    )

    # Collapse per-user / per-client_addr series into one merged distribution
    # per day, aligned as deltas (this metric is CUMULATIVE and resets
    # periodically, so raw values aren't directly comparable across points).
    aggregation = monitoring_v3.Aggregation(
        alignment_period={"seconds": 86400},  # 1 day
        per_series_aligner=monitoring_v3.Aggregation.Aligner.ALIGN_DELTA,
        cross_series_reducer=monitoring_v3.Aggregation.Reducer.REDUCE_SUM,
        group_by_fields=[],
    )

    metric_filter = (
        f'metric.type="{METRIC_TYPE}" '
        f'AND resource.type="cloudsql_instance_database" '
        f'AND resource.labels.resource_id="{project_id}:{instance_id}" '
        f'AND {SELECT_ONLY_FILTER}'
    )
    if database:
        metric_filter += f' AND resource.labels.database="{database}"'

    request = monitoring_v3.ListTimeSeriesRequest(
        name=project_name,
        filter=metric_filter,
        interval=interval,
        aggregation=aggregation,
        view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
    )

    rows = []
    for series in client.list_time_series(request=request):
        for point in series.points:
            dist = point.value.distribution_value
            if not dist.bucket_counts:
                continue
            edges = bucket_bounds_us(dist.bucket_options)
            day = point.interval.end_time.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            counts = list(dist.bucket_counts)
            # bucket_counts can be shorter than len(edges)-1; trailing buckets with 0 count are omitted
            for i, count in enumerate(counts):
                if count == 0:
                    continue
                lower = edges[i]
                upper = edges[i + 1] if i + 1 < len(edges) else np.inf
                rows.append(
                    {
                        "day": day,
                        "bucket_idx": i,
                        "lower_us": lower,
                        "upper_us": upper,
                        "count": count,
                    }
                )

    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError(
            "No data returned. Check that Query Insights is enabled on the "
            "instance and that the project/instance IDs are correct."
        )
    df["lower_ms"] = df["lower_us"] / 1000.0
    df["upper_ms"] = df["upper_us"] / 1000.0
    return df.sort_values(["day", "bucket_idx"]).reset_index(drop=True)


def summarize_and_plot(df: pd.DataFrame, out_prefix: str = "cloudsql_read_latency"):
    # --- Overall histogram across the full window ---
    overall = df.groupby(["bucket_idx", "lower_ms", "upper_ms"], as_index=False)["count"].sum()
    overall = overall.sort_values("bucket_idx")

    total = overall["count"].sum()
    cum = np.cumsum(overall["count"].to_numpy())
    pct = cum / total
    p50 = overall["lower_ms"].to_numpy()[np.searchsorted(pct, 0.50)]
    p95 = overall["lower_ms"].to_numpy()[np.searchsorted(pct, 0.95)]
    p99 = overall["lower_ms"].to_numpy()[np.searchsorted(pct, 0.99)]

    print(f"Total sampled SELECT statements: {int(total):,}")
    print(f"Approx p50 SELECT latency: {p50:.4f} ms")
    print(f"Approx p95 SELECT latency: {p95:.4f} ms")
    print(f"Approx p99 SELECT latency: {p99:.4f} ms")

    fig, axes = plt.subplots(2, 1, figsize=(11, 9))

    # Plot 1: overall histogram, log-scale x-axis since buckets are exponential
    ax = axes[0]
    ax.bar(overall["lower_ms"], overall["count"], width=np.diff(
        np.append(overall["lower_ms"].to_numpy(), overall["upper_ms"].iloc[-1])
    ), align="edge", edgecolor="black", linewidth=0.3)
    ax.set_xscale("log")
    ax.set_xlabel("Query latency (ms, log scale)")
    ax.set_ylabel("Query count")
    ax.set_title(f"SELECT latency distribution — full {df['day'].nunique()}-day window")
    for p, label in [(p50, "p50"), (p95, "p95"), (p99, "p99")]:
        ax.axvline(p, color="red", linestyle="--", linewidth=1)
        ax.text(p, ax.get_ylim()[1] * 0.9, label, color="red", rotation=90, va="top")

    # Plot 2: heatmap of bucket counts over time
    ax2 = axes[1]
    pivot = df.pivot_table(index="day", columns="lower_ms", values="count", aggfunc="sum", fill_value=0)
    pivot = pivot.sort_index(axis=1)
    data = np.log1p(pivot.to_numpy())  # log-scale color for readability
    im = ax2.pcolormesh(range(pivot.shape[1] + 1), range(pivot.shape[0] + 1), data, shading="flat", cmap="viridis")
    ax2.set_yticks(np.arange(pivot.shape[0]) + 0.5)
    ax2.set_yticklabels([d.strftime("%Y-%m-%d") for d in pivot.index])
    tick_step = max(1, pivot.shape[1] // 12)
    ax2.set_xticks(np.arange(0, pivot.shape[1], tick_step) + 0.5)
    ax2.set_xticklabels([f"{v:.1f}" for v in pivot.columns[::tick_step]], rotation=45, ha="right")
    ax2.set_xlabel("Latency bucket lower bound (ms)")
    ax2.set_ylabel("Day")
    ax2.set_title("SELECT latency distribution by day (color = log(count+1))")
    fig.colorbar(im, ax=ax2, label="log(count + 1)")

    fig.tight_layout()
    png_path = f"{out_prefix}.png"
    fig.savefig(png_path, dpi=150)
    print(f"Saved plot to {png_path}")

    csv_path = f"{out_prefix}.csv"
    df.to_csv(csv_path, index=False)
    print(f"Saved tidy data to {csv_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="GCP project ID")
    parser.add_argument("--instance", required=True, help="Cloud SQL instance ID (not the connection name)")
    parser.add_argument("--database", default=None, help="Optional: filter to a single database name")
    parser.add_argument("--weeks", type=int, default=6, help="How many weeks back to pull (default 6)")
    parser.add_argument("--out-prefix", default="cloudsql_read_latency", help="Output file prefix")
    args = parser.parse_args()

    df = fetch_daily_distributions(args.project, args.instance, args.weeks, args.database)
    summarize_and_plot(df, args.out_prefix)


if __name__ == "__main__":
    main()