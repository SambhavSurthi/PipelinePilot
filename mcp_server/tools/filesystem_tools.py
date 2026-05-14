import os

def read_file(file_path: str) -> str:
    """
    Reads local file and returns content.
    
    Args:
        file_path: Path to the local file.
        
    Returns:
        Content of the file as string.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        raise ValueError(f"Failed to read file: {e}")

def write_file(file_path: str, content: str) -> dict:
    """
    Writes content to file.
    
    Args:
        file_path: Path to the local file.
        content: The text content to write.
        
    Returns:
        Dictionary indicating success and path.
    """
    try:
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "path": file_path}
    except Exception as e:
        return {"success": False, "message": str(e), "path": file_path}

def list_directory(dir_path: str, recursive: bool = False) -> list[str]:
    """
    Lists files in a directory.
    
    Args:
        dir_path: Path to the local directory.
        recursive: Whether to list files recursively.
        
    Returns:
        List of file paths.
    """
    try:
        files_list = []
        if recursive:
            for root, dirs, files in os.walk(dir_path):
                for file in files:
                    files_list.append(os.path.join(root, file))
        else:
            for item in os.listdir(dir_path):
                full_path = os.path.join(dir_path, item)
                if os.path.isfile(full_path):
                    files_list.append(full_path)
        return files_list
    except Exception as e:
        raise ValueError(f"Failed to list directory: {e}")
