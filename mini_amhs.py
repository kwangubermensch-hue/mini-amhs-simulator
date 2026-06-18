"""
미니 AMHS 반송 시뮬레이터 — D-5 "돌아가는 깡통" (최소 실행 버전)
------------------------------------------------------------------
핵심 질문: 레일/스토커 배치를 바꾸면 반송 성능이 어떻게 달라지는가?
이 파일은 그 실험을 위한 '게임 엔진'의 가장 단순한 형태다.

구성 흐름(보드게임처럼 매 tick마다):
  1) 새 운반요청(콜) 생성  2) 빈 차에 배차  3) 차 한 칸 이동
  4) 도착 처리            5) 기록
"""

import random
import networkx as nx

random.seed(42)  # 재현 가능하게 (실험엔 필수)


# ──────────────────────────────────────────────────────────
# 1. 가상 팹 = 지하철 노선도(그래프)
#    노드 = 역(장비/스토커/교차점), 엣지 = 레일(가중치=이동시간)
# ──────────────────────────────────────────────────────────
def build_fab(rows=4, cols=4):
    """격자형 팹을 만든다. 나중에 layouts.py에서 이 부분을 바꿔가며 비교."""
    G = nx.grid_2d_graph(rows, cols)          # (r,c) 좌표가 노드가 됨
    for u, v in G.edges():
        G[u][v]["time"] = 1                   # 한 구간 이동 = 1 tick (단순화)

    # 역할 지정: 한 노드는 스토커(보관창고), 몇 노드는 장비(Tool)
    stocker = (0, 0)
    tools = [(0, cols - 1), (rows - 1, 0), (rows - 1, cols - 1), (rows // 2, cols // 2)]
    return G, stocker, tools


# ──────────────────────────────────────────────────────────
# 2. OHT 차량 — 현재 상태판
# ──────────────────────────────────────────────────────────
class Vehicle:
    def __init__(self, vid, pos):
        self.id = vid
        self.pos = pos          # 현재 위치(노드)
        self.path = []          # 남은 경로(노드 리스트)
        self.job = None         # 맡은 작업 (None이면 놀고 있음)
        self.busy_ticks = 0     # 가동률 계산용

    @property
    def idle(self):
        return self.job is None


# ──────────────────────────────────────────────────────────
# 3. 운반요청(Job) — "언제, 어디서, 어디로"
#    D-5는 단순 랜덤. (나중에 실제 공정순서로 고도화 가능)
# ──────────────────────────────────────────────────────────
class Job:
    def __init__(self, jid, src, dst, created):
        self.id = jid
        self.src = src
        self.dst = dst
        self.created = created      # 생성 시각
        self.done = None            # 완료 시각


# ──────────────────────────────────────────────────────────
# 4. 배차 두뇌 — "어느 빈 차를 보낼까"
#    여기만 갈아끼우며 비교한다 (dispatcher.py의 핵심)
# ──────────────────────────────────────────────────────────
def dispatch_nearest(G, job, idle_vehicles):
    """가장 가까운 빈 차를 고른다(최단경로 거리 기준)."""
    best, best_dist = None, float("inf")
    for v in idle_vehicles:
        d = nx.shortest_path_length(G, v.pos, job.src, weight="time")
        if d < best_dist:
            best, best_dist = v, d
    return best


# ──────────────────────────────────────────────────────────
# 5. 메인 루프 — 보드게임 진행자(sim.py)
# ──────────────────────────────────────────────────────────
def run(total_ticks=300, n_vehicles=3, job_rate=0.5, dispatcher=dispatch_nearest):
    G, stocker, tools = build_fab()
    vehicles = [Vehicle(i, stocker) for i in range(n_vehicles)]
    pending = []            # 아직 배차 안 된 콜
    completed = []          # 완료된 콜
    job_counter = 0

    for t in range(total_ticks):
        # (1) 새 콜 생성 — 확률적으로
        if random.random() < job_rate:
            src = random.choice([stocker] + tools)
            dst = random.choice([x for x in tools if x != src])
            pending.append(Job(job_counter, src, dst, t))
            job_counter += 1

        # (2) 배차: 빈 차가 있고 대기 콜이 있으면 매칭
        idle = [v for v in vehicles if v.idle]
        for job in list(pending):
            if not idle:
                break
            v = dispatcher(G, job, idle)
            # 경로 = (현위치→픽업지) + (픽업지→목적지)
            to_src = nx.shortest_path(G, v.pos, job.src, weight="time")
            to_dst = nx.shortest_path(G, job.src, job.dst, weight="time")
            v.path = to_src[1:] + to_dst[1:]   # 현위치 중복 제거
            v.job = job
            pending.remove(job)
            idle.remove(v)

        # (3)(4) 이동 & 도착 처리
        for v in vehicles:
            if not v.idle:
                v.busy_ticks += 1
                if v.path:
                    v.pos = v.path.pop(0)      # 한 칸 전진
                if not v.path:                 # 목적지 도착
                    v.job.done = t
                    completed.append(v.job)
                    v.job = None

    # (5) KPI 집계
    return summarize(completed, vehicles, total_ticks, len(pending))


def summarize(completed, vehicles, total_ticks, leftover):
    if completed:
        lead_times = [j.done - j.created for j in completed]
        avg_lead = sum(lead_times) / len(lead_times)
        max_lead = max(lead_times)
    else:
        avg_lead = max_lead = 0
    util = sum(v.busy_ticks for v in vehicles) / (len(vehicles) * total_ticks)
    return {
        "완료_운반수(처리량)": len(completed),
        "미처리_대기콜": leftover,
        "평균_반송완료시간": round(avg_lead, 2),
        "최대_반송완료시간": max_lead,
        "차량_가동률": round(util, 3),
    }


if __name__ == "__main__":
    result = run()
    print("=== 미니 AMHS 시뮬레이션 결과 (D-5 깡통) ===")
    for k, v in result.items():
        print(f"  {k:18s}: {v}")
