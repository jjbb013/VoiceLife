"""
Upload Router - 音频上传与触发分析
处理音频文件上传，保存临时文件并调用音频处理流水线
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from typing import Optional
import tempfile
import shutil
import os
import uuid
import logging

from app.services.audio_processor import process_audio
from app.db import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/upload", tags=["Upload"])

# 允许上传的音频 MIME 类型
ALLOWED_AUDIO_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/ogg",
    "audio/aac",
    "audio/mp4",
    "audio/x-m4a",
    "audio/flac",
    "audio/webm",
}

# 最大文件大小 100MB
MAX_FILE_SIZE = 100 * 1024 * 1024


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="上传音频文件并触发分析流水线",
    description="接收音频文件上传，保存到临时目录后调用音频处理服务完成声纹分离、转写、分析等全流程",
)
async def upload_audio(
    file: UploadFile = File(..., description="音频文件 (mp3, wav, ogg, m4a 等格式)"),
    user_id: str = Form(..., description="上传用户 ID"),
    is_meeting_mode: bool = Form(False, description="是否为会议模式"),
    lat: Optional[float] = Form(None, description="录音纬度坐标"),
    lng: Optional[float] = Form(None, description="录音经度坐标"),
):
    """
    上传音频文件，触发完整分析流水线。

    流程:
        1. 验证音频文件类型和大小
        2. 保存上传文件到临时目录
        3. 调用 process_audio() 进行声纹分离、转写、分析
        4. 保存结果到数据库
        5. 返回录音ID和分析结果
    """
    # 1. 验证文件类型
    content_type = file.content_type or ""
    if content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"不支持的音频格式: {content_type}。支持的格式: {', '.join(sorted(ALLOWED_AUDIO_TYPES))}",
        )

    # 2. 读取文件内容并检查大小
    file_content = await file.read()
    file_size = len(file_content)
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件大小 {file_size / 1024 / 1024:.2f}MB 超过限制 {MAX_FILE_SIZE / 1024 / 1024}MB",
        )
    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件内容为空",
        )

    # 3. 验证 user_id
    if not user_id or not user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id 不能为空",
        )

    tmp_path = None
    try:
        # 4. 保存到临时文件
        file_ext = os.path.splitext(file.filename or "audio.wav")[1].lower()
        if not file_ext:
            file_ext = ".wav"

        tmp_fd, tmp_path = tempfile.mkstemp(suffix=file_ext, prefix=f"ailife_{user_id}_")
        try:
            with os.fdopen(tmp_fd, "wb") as tmp_file:
                tmp_file.write(file_content)
        except Exception as e:
            os.close(tmp_fd)
            raise e

        # 5. 创建 recording 记录
        recording_id = str(uuid.uuid4())

        row = await db.fetchrow(
            """
            INSERT INTO recordings (id, user_id, filename, file_size, mime_type, status, is_meeting_mode, lat, lng)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING *
            """,
            recording_id, user_id, file.filename or "unknown.wav", file_size,
            content_type, "processing", is_meeting_mode, lat, lng,
        )

        if not row:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="创建录音记录失败",
            )

        # 6. 调用音频处理流水线 (异步)
        analysis = await process_audio(
            audio_path=tmp_path,
            recording_id=recording_id,
            user_id=user_id,
            is_meeting_mode=is_meeting_mode,
        )

        # 7. 更新 recording 状态为完成
        await db.execute(
            "UPDATE recordings SET status = $1, processed_at = NOW() WHERE id = $2",
            "completed", recording_id,
        )

        return {
            "data": {
                "recording_id": recording_id,
                "filename": file.filename,
                "file_size": file_size,
                "status": "completed",
                "analysis": analysis,
            },
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"音频处理失败: {str(e)}", exc_info=True)

        # 更新 recording 状态为失败 (如果有 recording_id)
        try:
            if "recording_id" in dir():
                await db.execute(
                    "UPDATE recordings SET status = $1, error_message = $2 WHERE id = $3",
                    "failed", str(e), recording_id,
                )
        except Exception:
            pass

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"音频处理失败: {str(e)}",
        )

    finally:
        # 8. 清理临时文件
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception as cleanup_error:
                logger.warning(f"临时文件清理失败: {cleanup_error}")


@router.get(
    "/status/{recording_id}",
    summary="获取音频处理状态",
    description="查询某个录音文件的处理状态",
)
async def get_upload_status(recording_id: str):
    """
    查询录音文件的处理状态。
    """
    try:
        row = await db.fetchrow(
            "SELECT * FROM recordings WHERE id = $1", recording_id
        )

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"录音记录不存在: {recording_id}",
            )

        return {"data": dict(row), "error": None}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询录音状态失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询失败: {str(e)}",
        )
