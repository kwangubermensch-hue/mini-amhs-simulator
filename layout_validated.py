"""
검증된 레이아웃 비교 — 시드 40개 평균 ± 편차 (정직한 최종 결과)
산출물: layout_validated.png
"""
import statistics
from mini_amhs import run, dispatch_nearest
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

LAYOUTS = {"Cluster": [(1, 1), (1, 2), (2, 1), (2, 2)],
           "Line":    [(1, 0), (1, 1), (1, 2), (1, 3)],
           "Spread":  [(0, 3), (3, 0), (3, 3), (2, 2)]}
TICKS, SEEDS = 1500, 40

means, stds = [], []
for name, tools in LAYOUTS.items():
    rates = []
    for s in range(SEEDS):
        r = run(tools, dispatcher=dispatch_nearest, n_vehicles=3, total_ticks=TICKS, seed=s)
        rates.append(r["장비_총_대기시간"] / (len(tools) * TICKS) * 100)
    means.append(statistics.mean(rates))
    stds.append(statistics.stdev(rates))
    print(f"{name:8s}: {means[-1]:.1f}% ± {stds[-1]:.1f}")

plt.figure(figsize=(7, 5))
colors = ["#e03030", "#e0a030", "#3060e0"]
bars = plt.bar(list(LAYOUTS.keys()), means, yerr=stds, capsize=8,
               color=colors, alpha=0.85, edgecolor="black")
for b, m in zip(bars, means):
    plt.text(b.get_x() + b.get_width() / 2, m + 0.3, f"{m:.1f}%", ha="center", fontweight="bold")
plt.ylabel("Tool starvation rate (%)  ·  lower = better")
plt.title(f"Layout vs Tool Starvation (mean ± SD, {SEEDS} seeds, {TICKS} ticks)")
plt.grid(axis="y", alpha=0.3)
plt.tight_layout()
plt.savefig("layout_validated.png", dpi=120, bbox_inches="tight")
print("saved layout_validated.png")
