"""
거리 vs 분산 트레이드오프 — 혼잡(용량1) 하에서 차량 수에 따른 굶주림 교차
산출물: tradeoff_crossover.png
"""
from mini_amhs import run, dispatch_nearest
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CLUSTER = [(1, 1), (1, 2), (2, 1), (2, 2)]
SPREAD = [(0, 3), (3, 0), (3, 3), (2, 2)]
veh_range = list(range(2, 15))

cluster_starve, spread_starve = [], []
for n in veh_range:
    cluster_starve.append(run(CLUSTER, dispatcher=dispatch_nearest, edge_capacity=1, n_vehicles=n)["장비_총_대기시간"])
    spread_starve.append(run(SPREAD, dispatcher=dispatch_nearest, edge_capacity=1, n_vehicles=n)["장비_총_대기시간"])

plt.figure(figsize=(9, 5.5))
plt.plot(veh_range, cluster_starve, "o-", color="#e03030", lw=2, label="Cluster (short trips)")
plt.plot(veh_range, spread_starve, "s-", color="#3060e0", lw=2, label="Spread (distributed)")

# 교차점 표시
for i in range(1, len(veh_range)):
    if (cluster_starve[i - 1] < spread_starve[i - 1]) != (cluster_starve[i] < spread_starve[i]):
        xc = veh_range[i]
        plt.axvline(xc, color="gray", ls="--", alpha=0.6)
        plt.text(xc + 0.1, max(max(cluster_starve), max(spread_starve)) * 0.9,
                 "ranking flips", color="gray")
        break

plt.xlabel("Number of vehicles")
plt.ylabel("Total tool starvation (lower = better)")
plt.title("Distance vs Distribution trade-off (with rail congestion, capacity=1)")
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()
plt.savefig("tradeoff_crossover.png", dpi=120, bbox_inches="tight")
print("saved tradeoff_crossover.png")
print("cluster:", cluster_starve)
print("spread :", spread_starve)
