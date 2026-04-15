"""소형 CNN·GNN(순수 torch). PyTorch Geometric 미사용."""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class TinyWallCNN(nn.Module):
    """입력 (B,1,S,S) 선분 래스터 → (B,1,S,S) 마스크 로짓."""

    def __init__(self, size: int = 64):
        super().__init__()
        self.size = size
        self.enc = nn.Sequential(
            nn.Conv2d(1, 16, 3, padding=1),
            nn.ReLU(),
            nn.Conv2d(16, 32, 3, padding=1),
            nn.ReLU(),
            nn.Conv2d(32, 32, 3, padding=1),
            nn.ReLU(),
        )
        self.dec = nn.Sequential(
            nn.Conv2d(32, 16, 3, padding=1),
            nn.ReLU(),
            nn.Conv2d(16, 1, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.enc(x)
        return self.dec(h)


def symmetric_normalized_adjacency(num_nodes: int, edge_index: torch.Tensor) -> torch.Tensor:
    """무향 edge_index (2,E) → Â = D^{-1/2} (A+I) D^{-1/2}."""
    if num_nodes <= 0:
        return torch.zeros(0, 0)
    A = torch.zeros(num_nodes, num_nodes, dtype=torch.float32)
    if edge_index.numel() > 0:
        ei = edge_index[0].long()
        ej = edge_index[1].long()
        A[ei, ej] = 1.0
        A[ej, ei] = 1.0
    A.fill_diagonal_(1.0)
    d = A.sum(dim=1).clamp(min=1e-6)
    d_inv_sqrt = d.pow(-0.5)
    return d_inv_sqrt.unsqueeze(1) * A * d_inv_sqrt.unsqueeze(0)


class TinySegGNN(nn.Module):
    """노드 특징 (N,F) → 노드 로짓 (N,1)."""

    def __init__(self, in_dim: int = 5, hidden: int = 32):
        super().__init__()
        self.lin1 = nn.Linear(in_dim, hidden)
        self.lin2 = nn.Linear(hidden, hidden)
        self.lin3 = nn.Linear(hidden, 1)

    def forward(self, x: torch.Tensor, adj: torch.Tensor) -> torch.Tensor:
        h = F.relu(self.lin1(x))
        h = adj @ h
        h = F.relu(self.lin2(h))
        h = adj @ h
        return self.lin3(h).squeeze(-1)


def nearest_node_index(mids: torch.Tensor, qx: float, qy: float) -> int:
    if mids.numel() == 0:
        return -1
    dx = mids[:, 0] - qx
    dy = mids[:, 1] - qy
    d2 = dx * dx + dy * dy
    return int(torch.argmin(d2).item())
