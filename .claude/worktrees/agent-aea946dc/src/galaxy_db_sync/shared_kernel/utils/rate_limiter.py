"""
API 速率限制器
"""

import asyncio
import time
from typing import Callable, Any, Optional
from ..exceptions import APIError, APIRateLimitError


class RateLimiter:
    """API 速率限制器，使用令牌桶算法控制并发和频率"""

    def __init__(self, max_concurrent: int = 5, calls_per_second: float = 10.0):
        """
        初始化速率限制器

        Args:
            max_concurrent: 最大并发数
            calls_per_second: 每秒最大调用次数
        """
        self.max_concurrent = max_concurrent
        self.calls_per_second = calls_per_second
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.min_interval = 1.0 / calls_per_second if calls_per_second > 0 else 0
        self.last_call_time = 0.0

    async def acquire(self):
        """获取执行许可"""
        await self.semaphore.acquire()

        # 控制调用频率
        if self.min_interval > 0:
            current_time = time.time()
            elapsed = current_time - self.last_call_time
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self.last_call_time = time.time()

    def release(self):
        """释放执行许可"""
        self.semaphore.release()

    async def execute_with_retry(
        self, func: Callable, *args, max_retries: int = 3, **kwargs
    ) -> Any:
        """
        执行函数并带重试机制

        Args:
            func: 要执行的函数
            args: 函数位置参数
            max_retries: 最大重试次数
            kwargs: 函数关键字参数

        Returns:
            函数执行结果

        Raises:
            APIError: 重试后仍失败
        """
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                await self.acquire()
                try:
                    return (
                        await func(*args, **kwargs)
                        if asyncio.iscoroutinefunction(func)
                        else func(*args, **kwargs)
                    )
                finally:
                    self.release()
            except APIRateLimitError as e:
                last_exception = e
                if attempt < max_retries:
                    # 指数退避策略
                    wait_time = min(2**attempt, 60)  # 最大等待60秒
                    await asyncio.sleep(wait_time)
                else:
                    raise
            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    # 指数退避策略
                    wait_time = min(2**attempt, 60)  # 最大等待60秒
                    await asyncio.sleep(wait_time)
                else:
                    raise APIError(f"API 调用失败，已重试 {max_retries} 次: {str(e)}")

        # 如果所有重试都失败了，抛出最后一次异常
        if last_exception:
            raise last_exception


# 全局速率限制器实例
default_rate_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    """获取全局速率限制器实例"""
    return default_rate_limiter
