"""
神经网络模块
实现GAT编码器、Actor网络、Critic网络、协商网络
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GATConv, global_mean_pool


class GATEncoder(nn.Module):
    """GAT编码器：用于状态编码"""
    
    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 128,
        num_layers: int = 3,
        num_heads: int = 4,
        dropout: float = 0.1
    ):
        """
        初始化GAT编码器
        
        Args:
            input_dim: 输入特征维度
            hidden_dim: 隐藏层维度
            num_layers: GAT层数
            num_heads: 注意力头数
            dropout: Dropout比率
        """
        super(GATEncoder, self).__init__()
        
        self.num_layers = num_layers
        self.convs = nn.ModuleList()
        
        # 第一层
        self.convs.append(
            GATConv(input_dim, hidden_dim, heads=num_heads, dropout=dropout, concat=True)
        )
        
        # 中间层
        for _ in range(num_layers - 2):
            self.convs.append(
                GATConv(
                    hidden_dim * num_heads,
                    hidden_dim,
                    heads=num_heads,
                    dropout=dropout,
                    concat=True
                )
            )
        
        # 最后一层（不concat，输出单一向量）
        if num_layers > 1:
            self.convs.append(
                GATConv(
                    hidden_dim * num_heads,
                    hidden_dim,
                    heads=1,
                    dropout=dropout,
                    concat=False
                )
            )
        
        self.dropout = nn.Dropout(dropout)
    
    def forward(self, x, edge_index, batch=None):
        """
        前向传播
        
        Args:
            x: 节点特征 [num_nodes, input_dim]
            edge_index: 边索引 [2, num_edges]
            batch: 批次索引（用于图池化）
        
        Returns:
            图嵌入向量 [batch_size, hidden_dim] 或 [num_nodes, hidden_dim]
        """
        # GAT层
        for i, conv in enumerate(self.convs):
            x = conv(x, edge_index)
            if i < len(self.convs) - 1:
                x = F.elu(x)
                x = self.dropout(x)
        
        # 如果提供了batch，进行图池化
        if batch is not None:
            x = global_mean_pool(x, batch)
        
        return x


class ActorNetwork(nn.Module):
    """Actor网络：输出动作概率分布"""
    
    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        hidden_dims: list = [256, 128]
    ):
        """
        初始化Actor网络
        
        Args:
            state_dim: 状态维度
            action_dim: 动作维度
            hidden_dims: 隐藏层维度列表
        """
        super(ActorNetwork, self).__init__()
        
        layers = []
        input_dim = state_dim
        
        for hidden_dim in hidden_dims:
            layers.append(nn.Linear(input_dim, hidden_dim))
            layers.append(nn.ReLU())
            input_dim = hidden_dim
        
        # 输出层
        layers.append(nn.Linear(input_dim, action_dim))
        layers.append(nn.Softmax(dim=-1))
        
        self.network = nn.Sequential(*layers)
    
    def forward(self, state):
        """
        前向传播
        
        Args:
            state: 状态向量 [batch_size, state_dim]
        
        Returns:
            动作概率分布 [batch_size, action_dim]
        """
        return self.network(state)


class CriticNetwork(nn.Module):
    """Critic网络：评估状态-动作值"""
    
    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        hidden_dims: list = [512, 256, 128]
    ):
        """
        初始化Critic网络
        
        Args:
            state_dim: 状态维度
            action_dim: 动作维度
            hidden_dims: 隐藏层维度列表
        """
        super(CriticNetwork, self).__init__()
        
        layers = []
        input_dim = state_dim + action_dim
        
        for hidden_dim in hidden_dims:
            layers.append(nn.Linear(input_dim, hidden_dim))
            layers.append(nn.ReLU())
            input_dim = hidden_dim
        
        # 输出层（Q值）
        layers.append(nn.Linear(input_dim, 1))
        
        self.network = nn.Sequential(*layers)
    
    def forward(self, state, action):
        """
        前向传播
        
        Args:
            state: 状态向量 [batch_size, state_dim]
            action: 动作向量 [batch_size, action_dim]
        
        Returns:
            Q值 [batch_size, 1]
        """
        x = torch.cat([state, action], dim=-1)
        return self.network(x)


class NegotiationNetwork(nn.Module):
    """协商网络：用于边界协商决策"""
    
    def __init__(
        self,
        input_dim: int,
        hidden_dims: list = [128, 64],
        output_dim: int = 1
    ):
        """
        初始化协商网络
        
        Args:
            input_dim: 输入维度（协商状态+历史案例特征）
            hidden_dims: 隐藏层维度列表
            output_dim: 输出维度（协商决策：接受/拒绝）
        """
        super(NegotiationNetwork, self).__init__()
        
        layers = []
        current_dim = input_dim
        
        for hidden_dim in hidden_dims:
            layers.append(nn.Linear(current_dim, hidden_dim))
            layers.append(nn.ReLU())
            current_dim = hidden_dim
        
        # 输出层
        layers.append(nn.Linear(current_dim, output_dim))
        layers.append(nn.Sigmoid())  # 输出0-1之间的概率
        
        self.network = nn.Sequential(*layers)
    
    def forward(self, x):
        """
        前向传播
        
        Args:
            x: 输入特征 [batch_size, input_dim]
        
        Returns:
            协商决策概率 [batch_size, output_dim]
        """
        return self.network(x)


class CoordinatorNetwork(nn.Module):
    """协调者网络：PPO策略网络"""
    
    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        hidden_dims: list = [256, 128]
    ):
        """
        初始化协调者网络
        
        Args:
            state_dim: 状态维度（全局状态）
            action_dim: 动作维度（协调决策）
            hidden_dims: 隐藏层维度列表
        """
        super(CoordinatorNetwork, self).__init__()
        
        layers = []
        input_dim = state_dim
        
        for hidden_dim in hidden_dims:
            layers.append(nn.Linear(input_dim, hidden_dim))
            layers.append(nn.Tanh())
            input_dim = hidden_dim
        
        # 输出层（策略分布参数）
        self.mean_layer = nn.Linear(input_dim, action_dim)
        self.log_std_layer = nn.Linear(input_dim, action_dim)
        
        self.feature_layers = nn.Sequential(*layers)
    
    def forward(self, state):
        """
        前向传播
        
        Args:
            state: 状态向量 [batch_size, state_dim]
        
        Returns:
            (mean, log_std): 策略分布参数
        """
        x = self.feature_layers(state)
        mean = self.mean_layer(x)
        log_std = self.log_std_layer(x)
        log_std = torch.clamp(log_std, min=-20, max=2)  # 限制log_std范围
        
        return mean, log_std
    
    def sample(self, state):
        """
        从策略分布中采样动作
        
        Args:
            state: 状态向量 [batch_size, state_dim]
        
        Returns:
            (action, log_prob): 动作和对应的对数概率
        """
        mean, log_std = self.forward(state)
        std = torch.exp(log_std)
        
        # 采样
        normal = torch.distributions.Normal(mean, std)
        action = normal.sample()
        log_prob = normal.log_prob(action).sum(dim=-1, keepdim=True)
        
        return action, log_prob
    
    def evaluate(self, state, action):
        """
        评估动作的对数概率
        
        Args:
            state: 状态向量 [batch_size, state_dim]
            action: 动作向量 [batch_size, action_dim]
        
        Returns:
            log_prob: 对数概率
        """
        mean, log_std = self.forward(state)
        std = torch.exp(log_std)
        
        normal = torch.distributions.Normal(mean, std)
        log_prob = normal.log_prob(action).sum(dim=-1, keepdim=True)
        
        return log_prob

