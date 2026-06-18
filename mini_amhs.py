"""
미니 AMHS 반송 시뮬레이터 — D-4 (장비 대기시간 KPI + 배차 규칙 비교)
------------------------------------------------------------------
D-5 깡통에서 추가된 것:
  1) 장비를 '살아있는 존재'로: FOUP 받으면 PROCESS_TIME 동안 공정 →
     끝나면 다음 장비로 보낼 콜을 스스로 생성 → 다음 게 없으면 '굶은 시간' 카운트
  2) 핵심 KPI = '장비 총 대기시간(굶은 시간)' = 곧 가동률·양산
  3) 배차 규칙 2종 비교: 가장 가까운 차 vs 가장 한가한 차

설계 메모(백로그):
  - 공정시간은 지금 모든 장비 고정(PROCESS_TIME). 나중에 장비별 차등.
  - dispatcher는 '동일 인터페이스'로 비워둠 → 나중에 강화학습 두뇌를 그 자리에 꽂기만.
"""

import random
import networkx as nx

PROCESS_TIME = 8        # 장비가 FOUP 하나 공정하는 데 걸리는 시간(고정) — 나중에 차등
INITIAL_FOUPS = 6       # 팹 안을 순환하는 FOUP 총개수


# ──────────────────────────────────────────────────────────
# 1. 가상 팹 = 그래프 (나중에 layouts.py에서 이 부분을 바꿔가며 비교)
# ──────────────────────────────────────────────────────────
def build_fab(rows=4, cols=4):
    G = nx.grid_2d_graph(rows, cols)
    for u, v in G.edges():
        G[u][v]["time"] = 1
    stocker = (0, 0)
    tool_nodes = [(0, cols - 1), (rows - 1, 0), (rows - 1, cols - 1), (rows // 2, cols // 2)]
    return G, stocker, tool_nodes


# ──────────────────────────────────────────────────────────
# 2. 장비(Tool) — 이제 '살아있는 존재' (공정하고, 굶주린다)
# ──────────────────────────────────────────────────────────
class Tool:
    def __init__(self, node):
        self.node = node
        self.queue = 0            # 입력 대기 중인 FOUP 수
        self.proc_remaining = 0   # 공정 남은 시간 (0이면 안 하는 중)
        self.starve_ticks = 0     # 굶은 시간 누적 ← 핵심 KPI
        self.busy_ticks = 0       # 공정한 시간 누적 (가동률용)

    @property
    def processing(self):
        return self.proc_remaining > 0


# ──────────────────────────────────────────────────────────
# 3. OHT 차량
# ──────────────────────────────────────────────────────────
class Vehicle:
    def __init__(self, vid, pos):
        self.id = vid
        self.pos = pos
        self.path = []
        self.job = None
        self.busy_ticks = 0

    @property
    def idle(self):
        return self.job is None


# ──────────────────────────────────────────────────────────
# 4. 운반요청(Job) — 이제 장비가 공정 끝낼 때 '스스로' 생성
# ──────────────────────────────────────────────────────────
class Job:
    def __init__(self, src, dst, created):
        self.src = src
        self.dst = dst
        self.created = created
        self.done = None


# ──────────────────────────────────────────────────────────
# 5. 배차 두뇌 — 동일 인터페이스(G, job, idle) -> vehicle
#    이 자리에 나중에 강화학습 두뇌를 그대로 꽂을 수 있다.
# ──────────────────────────────────────────────────────────
def dispatch_nearest(G, job, idle_vehicles):
    """가장 가까운 빈 차."""
    return min(idle_vehicles,
               key=lambda v: nx.shortest_path_length(G, v.pos, job.src, weight="time"))


def dispatch_least_busy(G, job, idle_vehicles):
    """가장 한가한(덜 일한) 차 — 일을 고르게 나눠 특정 차 과부하 방지."""
    return min(idle_vehicles, key=lambda v: v.busy_ticks)


# ──────────────────────────────────────────────────────────
# 6. 메인 루프
# ──────────────────────────────────────────────────────────
def run(total_ticks=300, n_vehicles=3, dispatcher=dispatch_nearest, seed=42):
    random.seed(seed)
    G, stocker, tool_nodes = build_fab()
    tools = {n: Tool(n) for n in tool_nodes}
    vehicles = [Vehicle(i, stocker) for i in range(n_vehicles)]
    pending, completed = [], []

    # 초기 FOUP을 장비 큐에 흩뿌려 둔다 (순환 시작점)
    for _ in range(INITIAL_FOUPS):
        tools[random.choice(tool_nodes)].queue += 1

    for t in range(total_ticks):
        # (A) 장비 갱신: 공정 진행 / 완료 시 다음 장비로 콜 생성 / 굶주림 카운트
        for tool in tools.values():
            if tool.processing:
                tool.proc_remaining -= 1
                tool.busy_ticks += 1
                if tool.proc_remaining == 0:        # 공정 완료 → 다음 장비로 보낼 콜 생성
                    dst = random.choice([n for n in tool_nodes if n != tool.node])
                    pending.append(Job(tool.node, dst, t))
            if not tool.processing:                 # 안 하는 중이면
                if tool.queue > 0:                  # 큐에 있으면 다음 공정 시작
                    tool.queue -= 1
                    tool.proc_remaining = PROCESS_TIME
                else:                               # 없으면 → 굶는 중
                    tool.starve_ticks += 1

        # (B) 배차
        idle = [v for v in vehicles if v.idle]
        for job in list(pending):
            if not idle:
                break
            v = dispatcher(G, job, idle)
            to_src = nx.shortest_path(G, v.pos, job.src, weight="time")
            to_dst = nx.shortest_path(G, job.src, job.dst, weight="time")
            v.path = to_src[1:] + to_dst[1:]
            v.job = job
            pending.remove(job)
            idle.remove(v)

        # (C) 이동 & 배달
        for v in vehicles:
            if not v.idle:
                v.busy_ticks += 1
                if v.path:
                    v.pos = v.path.pop(0)
                if not v.path:                      # 목적지 도착 = 배달 완료
                    v.job.done = t
                    tools[v.job.dst].queue += 1      # 도착 장비 입력 큐 +1
                    completed.append(v.job)
                    v.job = None

    return summarize(tools, vehicles, completed, total_ticks, len(pending))


def summarize(tools, vehicles, completed, total_ticks, leftover):
    total_starve = sum(tl.starve_ticks for tl in tools.values())
    tool_util = sum(tl.busy_ticks for tl in tools.values()) / (len(tools) * total_ticks)
    veh_util = sum(v.busy_ticks for v in vehicles) / (len(vehicles) * total_ticks)
    return {
        "장비_총_대기시간(굶은tick)": total_starve,   # ★ 핵심 KPI (낮을수록 좋음)
        "장비_평균_가동률": round(tool_util, 3),
        "완료_운반수(처리량)": len(completed),
        "미처리_대기콜": leftover,
        "차량_가동률": round(veh_util, 3),
    }


if __name__ == "__main__":
    print("=== D-4: 배차 규칙 비교 ===")
    for name, disp in [("가까운 차", dispatch_nearest), ("한가한 차", dispatch_least_busy)]:
        r = run(dispatcher=disp)
        print(f"\n[{name}]")
        for k, v in r.items():
            print(f"  {k:22s}: {v}")
