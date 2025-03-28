import time

import psutil

from service.log import logger


class SystemMonitor:
    def __init__(self):
        self.has_gpu = self._check_gpu_availability()

    def _check_gpu_availability(self):
        try:
            import subprocess

            subprocess.check_output(["nvidia-smi"])
            return True
        except Exception as e:
            logger.warning(f"No GPU detected: {str(e)}")
            return False

    def get_system_info(self):
        """システムリソース情報の取得"""
        info = {
            "timestamp": time.time(),
            "cpu": {
                "total": psutil.cpu_percent(interval=None),
                "per_cpu": psutil.cpu_percent(interval=None, percpu=True),
                "memory": psutil.virtual_memory().percent,
            },
        }

        if self.has_gpu:
            try:
                import subprocess

                cmd = "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits"
                output = subprocess.check_output(cmd.split(), universal_newlines=True)
                util, mem_used, mem_total = output.strip().split(",")

                info["gpu"] = {
                    "utilization": float(util),
                    "memory_used": float(mem_used),
                    "memory_total": float(mem_total),
                }
            except Exception as e:
                logger.error(f"GPU info error: {str(e)}")

        return info
