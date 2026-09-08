"""Hot-path extraction: Tarjan SCC collapse, then longest path on the DAG.

A CFG with loops has no longest path, so loops are collapsed to a single
representative carrying the summed rank of its members. The path is expanded
back to real node ids before it is returned.
"""


def find_sccs(nodes: dict, edges: list) -> list[set[int]]:
    """Tarjan's SCC algorithm for loop-collapse in hot path computation."""
    adj: dict[int, list[int]] = {n: [] for n in nodes}
    for e in edges:
        if e.src in adj:
            adj[e.src].append(e.dst)
    index_counter = [0]
    stack: list[int] = []
    lowlink: dict[int, int] = {}
    index: dict[int, int] = {}
    on_stack: set[int] = set()
    sccs: list[set[int]] = []

    def strongconnect(v: int) -> None:
        index[v] = lowlink[v] = index_counter[0]
        index_counter[0] += 1
        stack.append(v)
        on_stack.add(v)
        for w in adj.get(v, []):
            if w not in index:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], index[w])
        if lowlink[v] == index[v]:
            scc: set[int] = set()
            while True:
                w = stack.pop()
                on_stack.discard(w)
                scc.add(w)
                if w == v:
                    break
            if len(scc) > 1:
                sccs.append(scc)

    for v in nodes:
        if v not in index:
            strongconnect(v)
    return sccs


def longest_path_dag(nodes: dict, edges: list) -> list[int]:
    """Longest-path on the SCC-collapsed DAG. SCCs (loops) collapse to a
    representative node carrying the combined rank score."""
    if not nodes:
        return []
    sccs = find_sccs(nodes, edges)
    # Map each node to its SCC representative (min id in SCC)
    node_to_rep: dict[int, int] = {}
    rep_score: dict[int, float] = {}
    scc_members: dict[int, set[int]] = {}
    for scc in sccs:
        rep = min(scc)
        scc_members[rep] = scc
        rep_score[rep] = sum(nodes[n].rank_score for n in scc if n in nodes)
        for n in scc:
            node_to_rep[n] = rep
    # Nodes not in any SCC map to themselves
    for n in nodes:
        if n not in node_to_rep:
            node_to_rep[n] = n
            rep_score[n] = nodes[n].rank_score

    # Build DAG on representatives
    dag_nodes = set(node_to_rep.values())
    dag_adj: dict[int, list[tuple[int, float]]] = {n: [] for n in dag_nodes}
    seen_edges: set[tuple[int, int]] = set()
    for e in edges:
        u, v = node_to_rep.get(e.src, e.src), node_to_rep.get(e.dst, e.dst)
        if u != v and (u, v) not in seen_edges:
            dag_adj[u].append((v, e.probability))
            seen_edges.add((u, v))

    # Topological sort via Kahn's algorithm
    in_degree = {n: 0 for n in dag_nodes}
    for u in dag_adj:
        for v, _ in dag_adj[u]:
            in_degree[v] = in_degree.get(v, 0) + 1
    queue = sorted([n for n in dag_nodes if in_degree.get(n, 0) == 0])
    topo: list[int] = []
    while queue:
        u = queue.pop(0)
        topo.append(u)
        for v, _ in dag_adj.get(u, []):
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)
                queue.sort()

    # Longest path DP on DAG
    dist = {n: 0.0 for n in dag_nodes}
    parent = {n: -1 for n in dag_nodes}
    for u in topo:
        for v, w in dag_adj.get(u, []):
            score = dist[u] + rep_score.get(v, 0) * w
            if score > dist[v]:
                dist[v] = score
                parent[v] = u
    if not dist:
        return list(nodes.keys())[:1]
    end = max(dist, key=dist.get)
    path_reps: list[int] = []
    current = end
    while current != -1:
        path_reps.append(current)
        current = parent[current]
    path_reps.reverse()

    # Expand SCC representatives back to original nodes
    path: list[int] = []
    for rep in path_reps:
        if rep in scc_members:
            path.extend(sorted(scc_members[rep]))
        else:
            path.append(rep)
    return path


_find_sccs = find_sccs
_longest_path_dag = longest_path_dag
