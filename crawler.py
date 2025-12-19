import os
import re
import hashlib
import requests
from datetime import datetime
from bs4 import BeautifulSoup

# ===================== 日志配置 =====================
class LogColor:
    """日志颜色定义"""
    RESET = "\033[0m"
    RED = "\033[31m"    # 错误
    GREEN = "\033[32m"  # 成功
    YELLOW = "\033[33m" # 信息
    BLUE = "\033[34m"   # 调试
    CYAN = "\033[36m"   # 详情

# 日志级别配置
LOG_CONFIG = {
    "ERROR": (LogColor.RED, "ERROR"),
    "SUCCESS": (LogColor.GREEN, "SUCCESS"),
    "INFO": (LogColor.YELLOW, "INFO"),
    "DEBUG": (LogColor.BLUE, "DEBUG"),
    "DETAIL": (LogColor.CYAN, "DETAIL")
}

def log(message, level="INFO"):
    """输出格式化的日志信息"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    color, level_name = LOG_CONFIG.get(level.upper(), (LogColor.YELLOW, "INFO"))
    print(f"{color}[{timestamp}] [{level_name}] - {message}{LogColor.RESET}")

# ===================== MD5相关功能 =====================
def calculate_file_md5(file_path):
    """计算本地文件的MD5哈希值"""
    if not os.path.exists(file_path):
        log(f"文件不存在，无法计算MD5: {file_path}", "ERROR")
        return None
    
    md5_hash = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()
    except Exception as e:
        log(f"计算MD5失败: {e}", "ERROR")
        return None

def download_remote_md5(version_original, is_fabric, base_url, resource_pack_dir):
    """
    从服务器下载对应的MD5文件内容，并将MD5文件保存到资源包目录
    :param version_original: 原始带-的版本号
    :param is_fabric: 是否为Fabric版本
    :param base_url: 基础URL
    :param resource_pack_dir: 资源包保存目录（用于保存MD5文件）
    :return: 远程MD5值（字符串），失败返回None
    """
    # MD5文件名规则：1-xx.md5 / 1-xx-fabric.md5（完全保留-，不转.）
    md5_filename = f"{version_with_dots}{'-fabric' if is_fabric else ''}.md5"
    md5_url = f"{base_url}{md5_filename}"
    # 构建MD5文件的本地保存路径
    md5_save_path = os.path.join(resource_pack_dir, md5_filename)
    
    try:
        response = requests.get(md5_url, timeout=30)
        response.raise_for_status()
        # 提取MD5值（去除空格/换行）
        remote_md5 = response.text.strip()
        
        # ========== 新增：保存MD5文件到资源包目录 ==========
        try:
            with open(md5_save_path, 'w', encoding='utf-8') as f:
                f.write(remote_md5)
            log(f"成功保存MD5文件: {md5_save_path}", "DEBUG")
        except Exception as e:
            log(f"保存MD5文件失败 ({md5_save_path}): {e}", "ERROR")
        # ==================================================
        
        log(f"成功下载远程MD5: {md5_filename} -> {remote_md5}", "DEBUG")
        return remote_md5
    except requests.exceptions.RequestException as e:
        log(f"下载远程MD5失败 ({md5_url}): {e}", "ERROR")
        return None

def verify_file_md5(file_path, version_original, is_fabric, base_url, resource_pack_dir):
    """
    验证本地文件MD5与远程MD5是否一致（使用原始版本号）
    :param resource_pack_dir: 资源包保存目录（传递给download_remote_md5用于保存MD5文件）
    """
    # 获取本地MD5
    local_md5 = calculate_file_md5(file_path)
    if not local_md5:
        return False
    
    # 获取远程MD5（新增传递resource_pack_dir参数）
    remote_md5 = download_remote_md5(version_original, is_fabric, base_url, resource_pack_dir)
    if not remote_md5:
        return False
    
    # 对比MD5（忽略大小写）
    if local_md5.lower() == remote_md5.lower():
        log(f"MD5校验通过: {os.path.basename(file_path)}", "SUCCESS")
        return True
    else:
        log(f"MD5校验失败！本地: {local_md5} | 远程: {remote_md5}", "ERROR")
        # 校验失败时删除损坏文件
        try:
            os.remove(file_path)
            log(f"已删除损坏文件: {file_path}", "INFO")
        except Exception as e:
            log(f"删除损坏文件失败: {e}", "ERROR")
        return False

# ===================== 主程序 =====================
# 常量定义
BASE_URL = "http://8.137.167.65:64684/"  # 目标下载地址
RESOURCE_PACK_DIR = "resource_pack"       # 资源包保存目录

# 文件名匹配模式
FILE_PATTERN = r'Minecraft-Mod-Language-Modpack-(1-\d+(?:-\d+)?)(-Fabric)?\.zip'

# 创建保存目录
os.makedirs(RESOURCE_PACK_DIR, exist_ok=True)
log("目录准备完成", "DEBUG")

# 获取资源包列表页面
try:
    response = requests.get(BASE_URL, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    log("成功获取资源包列表页面", "SUCCESS")
except requests.exceptions.RequestException as e:
    log(f"获取页面失败: {e}", "ERROR")
    exit(1)

# 处理所有资源包链接
link_count = 0
skipped_count = 0
downloaded_count = 0
verified_count = 0

for link in soup.find_all('a'):
    href = link.get('href')
    
    # 检查是否是目标资源包文件
    if not href or "Minecraft-Mod-Language-Modpack-" not in href or not href.endswith('.zip'):
        continue
    
    link_count += 1
    # 完全保留服务器原始文件名，不做任何修改
    original_filename = href.split('/')[-1]
    log(f"发现资源包: {original_filename}", "DEBUG")
    
    # 解析文件名（仅提取版本和Fabric标识，不转换版本号）
    match = re.match(FILE_PATTERN, original_filename)
    if not match:
        log(f"文件名格式不符合要求，跳过: {original_filename}", "ERROR")
        continue
    
    version_original = match.group(1)     # 原始版本号（如1-12-2，保留-，不转.）
    is_fabric = match.group(2) is not None  # 是否为Fabric版本
    version_with_dots = version_original.replace ('-', '.')
    
    # 移除了过滤1-12-2-Fabric文件的逻辑，所有版本都处理
    log(f"解析结果 - 原始版本: {version_original}, Fabric: {is_fabric}", "DETAIL")
    
    # 构建完整下载URL和本地保存路径（完全保留原始文件名）
    file_url = href if href.startswith('http') else f"{BASE_URL}{href}"
    file_path = os.path.join(RESOURCE_PACK_DIR, original_filename)
    
    # 先检查文件是否存在，存在则验证MD5
    if os.path.exists(file_path):
        log(f"文件已存在，开始MD5校验: {original_filename}", "INFO")
        # 新增传递RESOURCE_PACK_DIR参数
        if verify_file_md5(file_path, version_original, is_fabric, BASE_URL, RESOURCE_PACK_DIR):
            skipped_count += 1
            verified_count += 1
            continue
        else:
            log(f"MD5校验失败，将重新下载: {original_filename}", "INFO")
    
    # 下载资源包文件（保留原始文件名）
    log(f"开始下载资源包: {original_filename}", "INFO")
    try:
        response = requests.get(file_url, timeout=30, stream=True)
        response.raise_for_status()
        
        # 分块保存文件（适合大文件，避免内存溢出）
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        log(f"资源包下载完成: {file_path}", "SUCCESS")
        downloaded_count += 1
    except requests.exceptions.RequestException as e:
        log(f"资源包下载失败 ({file_url}): {e}", "ERROR")
        # 清理未下载完成的文件
        if os.path.exists(file_path):
            os.remove(file_path)
        continue
    
    # 下载完成后立即校验MD5（新增传递RESOURCE_PACK_DIR参数）
    if verify_file_md5(file_path, version_original, is_fabric, BASE_URL, RESOURCE_PACK_DIR):
        verified_count += 1

# 输出统计信息（移除了忽略1-12-2-Fabric的统计项）
log("="*50, "INFO")
log(f"处理完成统计：", "SUCCESS")
log(f"  - 发现资源包总数: {link_count}", "INFO")
log(f"  - 成功下载文件数: {downloaded_count}", "INFO")
log(f"  - 跳过的有效文件数: {skipped_count}", "INFO")
log(f"  - MD5校验通过总数: {verified_count}", "INFO")