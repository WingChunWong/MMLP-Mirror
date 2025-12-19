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
    """
    输出格式化的日志信息
    
    Args:
        message: 日志内容
        level: 日志级别 (ERROR/SUCCESS/INFO/DEBUG/DETAIL)
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    color, level_name = LOG_CONFIG.get(level.upper(), (LogColor.YELLOW, "INFO"))
    print(f"{color}[{timestamp}] [{level_name}] - {message}{LogColor.RESET}")

def calculate_file_md5(file_path):
    """计算文件的MD5哈希值"""
    md5_hash = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5_hash.update(chunk)
        return md5_hash.hexdigest().lower()  # 返回小写形式的MD5
    except FileNotFoundError:
        return None
    except Exception as e:
        log(f"计算MD5失败: {e}", "ERROR")
        return None

def get_remote_md5(version, is_fabric):
    """从服务器获取指定版本的MD5值"""
    # 构建MD5文件名
    version_for_md5 = version.replace('-', '.')  # 将1-xx-x转换为1.xx.x
    md5_filename = f"{version_for_md5}-fabric.md5" if is_fabric else f"{version_for_md5}.md5"
    md5_url = f"{BASE_URL}{md5_filename}"
    
    try:
        log(f"尝试获取MD5文件: {md5_url}", "DEBUG")
        response = requests.get(md5_url, timeout=30)
        response.raise_for_status()
        remote_md5 = response.text.strip().lower()  # 转换为小写形式
        
        # 验证MD5格式
        if re.match(r'^[a-fA-F0-9]{32}$', remote_md5):
            log(f"成功获取远程MD5: {remote_md5[:16]}...", "SUCCESS")
            return remote_md5
        else:
            log(f"远程MD5格式无效: {remote_md5}", "ERROR")
            return None
    except requests.exceptions.RequestException as e:
        log(f"获取远程MD5失败: {e}", "ERROR")
        return None

def save_md5_file(version, is_fabric, md5_hash):
    """保存MD5哈希到本地文件"""
    # 构建MD5文件名
    version_for_md5 = version.replace('-', '.')  # 将1-xx-x转换为1.xx.x
    md5_filename = f"{version_for_md5}-fabric.md5" if is_fabric else f"{version_for_md5}.md5"
    md5_file = os.path.join(TARGET_DIR, md5_filename)
    
    try:
        # 确保保存的是小写形式的MD5
        with open(md5_file, 'w') as f:
            f.write(md5_hash.lower())
        log(f"MD5文件保存成功: {md5_file}", "SUCCESS")
        return True
    except Exception as e:
        log(f"保存MD5文件失败: {e}", "ERROR")
        return False

# ===================== 主程序 =====================
# 常量定义
BASE_URL = "http://8.137.167.65:64684/"  # 服务器地址
TARGET_DIR = "resource_pack"              # 保存目录

# 创建保存目录
os.makedirs(TARGET_DIR, exist_ok=True)

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

for link in soup.find_all('a'):
    href = link.get('href')
    
    # 检查是否是资源包文件
    if not href or "Minecraft-Mod-Language-Modpack-" not in href or not href.endswith('.zip'):
        continue
    
    link_count += 1
    filename = href.split('/')[-1]
    log(f"发现资源包: {filename}", "DEBUG")
    
    # 解析文件名（新命名规则）
    # 匹配格式: Minecraft-Mod-Language-Modpack-1-xx(-x)?(-Fabric)?.zip
    # 其中(-x)?表示可能有第三个版本号，(-Fabric)?表示可能有Fabric标识
    pattern = r'Minecraft-Mod-Language-Modpack-(1-\d+(?:-\d+)?)(-Fabric)?\.zip'
    match = re.match(pattern, filename)
    
    if not match:
        log(f"文件名格式错误: {filename}", "ERROR")
        continue
    
    version = match.group(1)  # 版本号，如1-19或1-19-2
    is_fabric = match.group(2) is not None  # 是否为fabric版本
    
    log(f"解析结果 - 版本: {version}, Fabric: {is_fabric}", "DETAIL")
    
    # 构建完整URL
    file_url = href if href.startswith('http') else f"{BASE_URL}{href}"
    
    # 检查本地是否已存在该文件
    file_path = os.path.join(TARGET_DIR, filename)
    
    # 获取远程MD5值
    remote_md5 = get_remote_md5(version, is_fabric)
    if not remote_md5:
        log(f"无法获取远程MD5，跳过下载: {filename}", "ERROR")
        continue
    
    if os.path.exists(file_path):
        # 计算本地文件的MD5
        local_md5 = calculate_file_md5(file_path)
        if local_md5:
            # 检查MD5是否匹配（忽略大小写）
            if local_md5.lower() == remote_md5.lower():
                log(f"文件已存在且MD5相同，跳过下载: {filename}", "INFO")
                log(f"本地MD5: {local_md5[:16]}..., 远程MD5: {remote_md5[:16]}...", "DETAIL")
                
                # 每次都要保存MD5文件，确保本地MD5文件是最新的
                save_md5_file(version, is_fabric, remote_md5)
                skipped_count += 1
                continue
            else:
                log(f"文件已存在但MD5不同，重新下载: {filename}", "INFO")
                log(f"本地MD5: {local_md5[:16]}..., 远程MD5: {remote_md5[:16]}...", "DETAIL")
        else:
            log(f"文件已存在但无法计算MD5，重新下载: {filename}", "INFO")
    else:
        log(f"文件不存在，开始下载: {filename}", "INFO")
    
    # 下载文件
    log(f"开始下载: {filename}", "INFO")
    try:
        response = requests.get(file_url, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        log(f"下载失败 - 文件: {filename}, 错误: {e}", "ERROR")
        continue
    
    # 保存文件
    with open(file_path, 'wb') as f:
        f.write(response.content)
    log(f"文件保存成功: {file_path}", "SUCCESS")
    downloaded_count += 1
    
    # 验证下载文件的MD5
    file_md5 = calculate_file_md5(file_path)
    if file_md5:
        # 比较MD5时忽略大小写
        if file_md5.lower() == remote_md5.lower():
            log(f"MD5验证通过 - 文件: {filename}", "SUCCESS")
            log(f"计算MD5: {file_md5[:16]}..., 期望MD5: {remote_md5[:16]}...", "DETAIL")
            
            # 保存MD5文件到资源包文件夹（每次下载后都保存）
            save_md5_file(version, is_fabric, remote_md5)
        else:
            log(f"MD5验证失败 - 文件: {filename}", "ERROR")
            log(f"计算MD5: {file_md5[:16]}..., 期望MD5: {remote_md5[:16]}...", "DETAIL")
    else:
        log(f"无法计算下载文件的MD5: {filename}", "ERROR")

# 输出统计信息
log(f"处理完成，共发现 {link_count} 个资源包文件", "SUCCESS")
log(f"下载了 {downloaded_count} 个文件，跳过了 {skipped_count} 个文件", "INFO")
if skipped_count > 0:
    log(f"跳过的文件: {skipped_count} 个（MD5哈希未变化）", "DETAIL")