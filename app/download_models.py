#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FunASR模型下载脚本
并行下载所有模型文件
"""
import logging
import sys
import json
import threading
from app.funasr_config import MODEL_REVISION, get_models_for_download
from app.logging_config import setup_logging

logger = logging.getLogger(__name__)


def download_model(model_config, progress_callback=None):
    """下载单个模型（使用 modelscope.snapshot_download，无需 funasr/torch）"""
    model_name = model_config["name"]
    model_type = model_config["type"]

    try:
        from modelscope.hub.snapshot_download import snapshot_download

        if progress_callback:
            progress_callback(model_type, "downloading", 0)

        # 下载到本地缓存目录
        snapshot_download(model_name, revision=MODEL_REVISION)

        if progress_callback:
            progress_callback(model_type, "completed", 100)

        return {"success": True, "model": model_type}

    except Exception as e:
        if progress_callback:
            progress_callback(model_type, "error", 0, str(e))
        return {"success": False, "model": model_type, "error": str(e)}

def main():
    """主函数：并行下载所有模型"""
    # 配置日志系统（使用统一配置）
    import os
    project_root = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(project_root, "logs")
    setup_logging("INFO", log_dir)
    
    # 从统一配置获取模型列表
    models = get_models_for_download()
    
    # 进度跟踪
    progress = {"asr": 0, "vad": 0, "punc": 0}
    results = {}
    completed_count = 0
    total_count = len(models)
    count_lock = threading.Lock()  # 添加锁保护计数器
    results_lock = threading.Lock()
    
    def progress_callback(model_type, stage, percent, error=None):
        nonlocal completed_count
        
        # 使用锁保护共享变量的修改
        with count_lock:
            if stage == "downloading":
                progress[model_type] = percent
            elif stage == "completed":
                progress[model_type] = 100
                completed_count += 1
            elif stage == "error":
                progress[model_type] = 0
                completed_count += 1
            
            # 计算总体进度
            overall_progress = sum(progress.values()) / total_count
            current_completed = completed_count
        
        # 输出进度信息（在锁外执行I/O操作）
        status = {
            "stage": stage,
            "model": model_type,
            "progress": percent,
            "overall_progress": round(overall_progress, 1),
            "completed": current_completed,
            "total": total_count
        }
        
        if error:
            status["error"] = error
            
        print(json.dumps(status, ensure_ascii=False))
        sys.stdout.flush()
    
    # 启动并行下载线程
    threads = []
    for model_config in models:
        def worker(config=model_config):
            result = download_model(config, progress_callback)
            with results_lock:
                results[config["type"]] = result

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        threads.append(thread)
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()
    
    # 检查结果
    failed_models = [model_type for model_type, result in results.items() if not result["success"]]
    
    if failed_models:
        final_result = {
            "success": False,
            "error": f"以下模型下载失败: {', '.join(failed_models)}",
            "failed_models": failed_models,
            "results": results
        }
    else:
        final_result = {
            "success": True,
            "message": "所有模型下载完成",
            "results": results
        }
    
    print(json.dumps(final_result, ensure_ascii=False))
    sys.stdout.flush()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        error_result = {
            "success": False,
            "error": str(e)
        }
        print(json.dumps(error_result, ensure_ascii=False))
        sys.exit(1)


def _project_models_dir():
    """项目内 models/ 目录路径。

    - 开发模式：<repo_root>/models/
    - 冻结模式 (PyInstaller)：<_MEIPASS>/models/（datas 解压目标，见 vocotype.spec）
    """
    import os
    import sys
    from pathlib import Path

    if getattr(sys, "frozen", False):
        # PyInstaller 把 datas 解压到 sys._MEIPASS；若拿不到，退到 exe 同目录
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        return Path(base) / "models"
    # app/download_models.py → app/ → repo_root/
    return Path(__file__).resolve().parent.parent / "models"


def _find_in_project_models(short_name):
    """在项目内 models/ 查找模型目录。

    支持两种存放结构：
      models/<short_name>/...
      models/iic/<short_name>/...
    """
    project = _project_models_dir()
    for candidate in (project / short_name, project / "iic" / short_name):
        if not candidate.exists():
            continue
        if (candidate / "model_quant.onnx").exists() or (candidate / "model.onnx").exists():
            return candidate
    return None


def get_model_cache_path(model_name, revision):
    """
    离线优先获取模型路径，查找顺序：
    1. 项目内 models/（开发模式：repo/models/；冻结模式：_MEIPASS/models/）— 用于离线分发
    2. 用户 modelscope 缓存（~/.cache/modelscope/...）
    3. modelscope 在线下载（最后兜底）
    """
    from pathlib import Path

    short_name = model_name.split('/')[-1] if '/' in model_name else model_name

    # 1. 项目内打包模型（最高优先级；离线分发场景的关键）
    project_match = _find_in_project_models(short_name)
    if project_match is not None:
        logger.info("使用项目内打包模型: %s", project_match)
        return str(project_match)

    # 2. 用户 modelscope 缓存
    cache_base = Path.home() / ".cache" / "modelscope" / "hub" / "models" / "iic"
    model_dir = cache_base / short_name
    if model_dir.exists():
        if (model_dir / "model_quant.onnx").exists() or (model_dir / "model.onnx").exists():
            logger.info("使用本地缓存模型: %s", model_dir)
            return str(model_dir)

    # 3. 本地都不存在，尝试 modelscope 下载
    logger.info("本地缓存不存在，开始下载模型: %s", model_name)
    from modelscope.hub.snapshot_download import snapshot_download
    try:
        # 先尝试纯离线模式（不联网，可能 modelscope 之前下了一部分但路径变了）
        model_dir = snapshot_download(
            model_name,
            revision=revision,
            local_files_only=True
        )
        logger.info("使用已下载的模型（离线模式）: %s", model_dir)
        return model_dir
    except Exception as offline_error:
        logger.warning("离线模式失败: %s，尝试在线下载", offline_error)
        model_dir = snapshot_download(model_name, revision=revision)
        logger.info("模型下载完成: %s", model_dir)
        return model_dir
