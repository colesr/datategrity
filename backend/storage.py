import os
from pathlib import Path
from fastapi import UploadFile
import aiofiles

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def project_folder(project_id: int) -> Path:
    path = UPLOAD_DIR / str(project_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


async def save_upload_file(project_id: int, upload_file: UploadFile) -> Path:
    destination = project_folder(project_id) / upload_file.filename
    async with aiofiles.open(destination, "wb") as out_file:
        content = await upload_file.read()
        await out_file.write(content)
    return destination


def dataset_path_for_project(project) -> Path:
    if not project or not project.dataset_path:
        return None
    return Path(project.dataset_path)


def get_dataset_path(project) -> str:
    path = dataset_path_for_project(project)
    return str(path) if path else None
