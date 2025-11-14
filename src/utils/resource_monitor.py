"""
资源监控模块
监控时间、内存等资源使用情况
"""

import time
import psutil
import os
from typing import Dict, Any, Optional
from contextlib import contextmanager


class ResourceMonitor:
    """资源监控器"""
    
    def __init__(self, enabled: bool = True):
        """
        初始化资源监控器
        
        Args:
            enabled: 是否启用监控
        """
        self.enabled = enabled
        self.process = psutil.Process(os.getpid())
        self.start_time = None
        self.start_memory = None
        self.peak_memory = 0.0
    
    def start(self):
        """开始监控"""
        if not self.enabled:
            return
        
        self.start_time = time.time()
        self.start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.peak_memory = self.start_memory
    
    def stop(self) -> Dict[str, float]:
        """
        停止监控并返回统计信息
        
        Returns:
            资源使用统计字典：
                - elapsed_time: 经过时间（秒）
                - memory_used: 使用的内存（MB）
                - peak_memory: 峰值内存（MB）
                - memory_increase: 内存增长（MB）
        """
        if not self.enabled or self.start_time is None:
            return {}
        
        elapsed_time = time.time() - self.start_time
        current_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = current_memory - self.start_memory
        
        if current_memory > self.peak_memory:
            self.peak_memory = current_memory
        
        return {
            'elapsed_time': elapsed_time,
            'memory_used': current_memory,
            'peak_memory': self.peak_memory,
            'memory_increase': memory_increase
        }
    
    def get_current_stats(self) -> Dict[str, float]:
        """
        获取当前资源使用统计
        
        Returns:
            当前资源使用统计
        """
        if not self.enabled:
            return {}
        
        current_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        if current_memory > self.peak_memory:
            self.peak_memory = current_memory
        
        elapsed_time = 0.0
        if self.start_time is not None:
            elapsed_time = time.time() - self.start_time
        
        return {
            'elapsed_time': elapsed_time,
            'memory_used': current_memory,
            'peak_memory': self.peak_memory
        }
    
    @contextmanager
    def monitor(self, label: str = ""):
        """
        上下文管理器，用于监控代码块
        
        Args:
            label: 监控标签
        
        Usage:
            with monitor.monitor("partition"):
                # 执行代码
                pass
        """
        self.start()
        try:
            yield
        finally:
            stats = self.stop()
            if label:
                print(f"[{label}] 资源使用: {stats}")
    
    def reset(self):
        """重置监控器"""
        self.start_time = None
        self.start_memory = None
        self.peak_memory = 0.0

