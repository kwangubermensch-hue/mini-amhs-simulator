"""
미니 AMHS 반송 시뮬레이터 — 엔진 (D-3: 레이아웃 비교 지원)
------------------------------------------------------------------
변경점:
  - build_fab / run 이 '장비 배치(layout)'를 인자로 받는다 → 배치를 바꿔가며 비교
  - 매 이동마다 '레일 구간 사용량'을 기록 → 정체 히트맵의 원천 데이터
KPI(핵심): 장비 총 대기시간(굶은 tick). 낮을수록 좋음 = 가동률·양산↑
"""

import random
import networkx as nx

PROCESS_TIME = 8
INITIAL_FOUPS = 12
STOCKER = (0, 0)


def build_fab(tool_nodes, rows=4, cols=4):
    """격자 레일 위에 '장비 배치(tool_nodes)'를 얹는다."""
    G = nx.grid_2d_graph(rows, cols)
    for u, v in G.edges():
        G[u][v]["time"] = 1
    return G


class Tool:
    def __init__(self, node):
        self.node = node
        self.queue = 0
        self.proc_remaining = 0
        self.starve_ticks = 0
        self.busy_ticks = 0

    @property
    def processing(self):
        return self.proc_remaining > 0


class Vehicle:
    def __init__(self, vid, pos):
        self.id, self.pos, self.path, self.job, self.busy_ticks = vid, pos, [], None, 0

    @property
    def idle(self):
        return self.job is None


class Job:
    def __init__(self, src, dst, created):
        self.src, self.dst, self.created, self.done = src, dst, created, None


def dispatch_nearest(G, job, idle_vehicles):
    return min(idle_vehicles,
               key=lambda v: nx.shortest_path_length(G, v.pos, job.src, weight="time"))


def dispatch_least_busy(G, job, idle_vehicles):
    return min(idle_vehicles, key=lambda v: v.busy_ticks)


def run(tool_nodes, total_ticks=300, n_vehicles=3, dispatcher=dispatch_nearest,
        edge_capacity=None, seed=42):
    random.seed(seed)
    G = build_fab(tool_nodes)
    tools = {n: Tool(n) for n in tool_nodes}
    vehicles = [Vehicle(i, STOCKER) for i in range(n_vehicles)]
    pending, completed = [], []
    edge_usage = {}                      # ← 레일 구간별 통행량(정체 히트맵 원천)
    congestion_wait = 0                  # 혼잡으로 차가 못 가고 기다린 tick 누적

    for _ in range(INITIAL_FOUPS):
        tools[random.choice(tool_nodes)].queue += 1

    for t in range(total_ticks):
        # (A) 장비: 공정 / 완료 시 콜 생성 / 굶주림
        for tool in tools.values():
            if tool.processing:
                tool.proc_remaining -= 1
                tool.busy_ticks += 1
                if tool.proc_remaining == 0:
                    dst = random.choice([n for n in tool_nodes if n != tool.node])
                    pending.append(Job(tool.node, dst, t))
            if not tool.processing:
                if tool.queue > 0:
                    tool.queue -= 1
                    tool.proc_remaining = PROCESS_TIME
                else:
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

        # (C) 이동 & 배달 — 레일 용량 제한(혼잡) 반영
        occ = {}                                 # 이번 tick에 각 레일을 점유한 차 수
        for v in vehicles:
            if not v.idle:
                v.busy_ticks += 1                # 일하는 중(기다려도 busy)
                if v.path:
                    nxt = v.path[0]
                    key = tuple(sorted([v.pos, nxt]))
                    # 용량 제한 없거나(None), 아직 여유 있으면 → 전진
                    if edge_capacity is None or occ.get(key, 0) < edge_capacity:
                        occ[key] = occ.get(key, 0) + 1
                        v.pos = v.path.pop(0)
                        edge_usage[key] = edge_usage.get(key, 0) + 1
                    else:
                        congestion_wait += 1     # 꽉 참 → 이 tick은 못 가고 대기
                if not v.path and v.job is not None:
                    v.job.done = t
                    tools[v.job.dst].queue += 1
                    completed.append(v.job)
                    v.job = None

    total_starve = sum(tl.starve_ticks for tl in tools.values())
    return {
        "장비_총_대기시간": total_starve,
        "장비_평균_가동률": round(sum(tl.busy_ticks for tl in tools.values()) / (len(tools) * total_ticks), 3),
        "처리량": len(completed),
        "차량_가동률": round(sum(v.busy_ticks for v in vehicles) / (len(vehicles) * total_ticks), 3),
        "정체_대기": congestion_wait,
        "_edge_usage": edge_usage,       # 내부용(히트맵). 출력 시 '_' 키는 건너뜀
    }


if __name__ == "__main__":
    DEFAULT = [(0, 3), (3, 0), (3, 3), (2, 2)]
    r = run(DEFAULT)
    for k, v in r.items():
        if not k.startswith("_"):
            print(f"  {k:14s}: {v}")
