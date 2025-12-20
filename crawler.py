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

# ===================== 计算哈希 =====================

def calculate_file_md5(file_path):
    """计算资源包的MD5哈希值"""
    md5_hash = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()
    except FileNotFoundError:
        return None
    except Exception as e:
        log(f"计算MD5失败: {e}", "ERROR")
        return None
    
def save_md5_hash(file_path, version, is_fabric):
    """计算并保存文件的MD5哈希值"""
    md5_value = calculate_file_md5(file_path)
    if md5_value:
        md5_filename = f"{version}-fabric.md5" if is_fabric else f"{version}.md5"
        md5_file = os.path.join(RESOURCE_PACK_DIR, md5_filename)
        
        try:
            with open(md5_file, 'w') as f:
                f.write(md5_value)
            log(f"MD5文件保存成功: {md5_file}", "SUCCESS")
            return md5_value
        except Exception as e:
            log(f"保存MD5文件失败: {e}", "ERROR")
    return None

def generate_new_filename(version, is_fabric):
    """生成新的文件名格式"""
    if version == "1.12.2":
        # 1.12.2 特殊版本
        return "Minecraft-Mod-Language-Modpack.zip"
    else:
        # 将版本号中的点替换为短横线
        version_new = version.replace('.', '-')
        if is_fabric:
            return f"Minecraft-Mod-Language-Modpack-{version_new}-Fabric.zip"
        else:
            return f"Minecraft-Mod-Language-Modpack-{version_new}.zip"

# ===================== 主程序 =====================
# 常量定义
BASE_URL = "https://cfpa.cyan.cafe/project-hex/"  # 列表页面
RESOURCE_PACK_DIR = "resource_pack"               # 资源包保存目录

# 修改正则表达式以匹配6位十六进制字符(根据实际文件名)
FILE_PATTERN = r'Minecraft-Mod-Language-Package-(1\.\d+(?:\.\d+)?)(?:-fabric)?-([a-fA-F0-9]{6})\.zip'  # 文件名模式

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

for link in soup.find_all('a'):
    href = link.get('href')
    
    # 检查是否是资源包文件
    if not href or "Minecraft-Mod-Language-Package-" not in href or not href.endswith('.zip'):
        continue
    
    link_count += 1
    filename = href.split('/')[-1]
    log(f"发现资源包: {filename}", "DEBUG")
    
    # 解析文件名
    match = re.match(FILE_PATTERN, filename)
    if not match:
        log(f"文件名格式错误: {filename}", "ERROR")
        continue
    
    version = match.group(1)          # 版本号
    remote_commit_hash = match.group(2)  # commit哈希值
    is_fabric = '-fabric' in filename  # 是否为fabric版本
    
    log(f"解析结果 - 版本: {version}, commit哈希: {remote_commit_hash}, Fabric: {is_fabric}", "DETAIL")
    
    # 生成新的文件名格式
    new_filename = generate_new_filename(version, is_fabric)
    
    # 构建完整URL
    file_url = href if href.startswith('http') else f"{BASE_URL}{href}"
    
    # 检查本地是否已存在该文件（使用新文件名格式）
    file_path = os.path.join(RESOURCE_PACK_DIR, new_filename)
    
    # 检查本地文件是否存在
    if os.path.exists(file_path):
        # 检查是否已有MD5文件（MD5文件名保持不变，使用原版本号）
        md5_filename = f"{version}-fabric.md5" if is_fabric else f"{version}.md5"
        md5_file = os.path.join(RESOURCE_PACK_DIR, md5_filename)
        
        if os.path.exists(md5_file):
            # 计算当前文件的MD5
            current_md5 = calculate_file_md5(file_path)
            
            # 读取已保存的MD5
            try:
                with open(md5_file, 'r') as f:
                    saved_md5 = f.read().strip()
                
                if current_md5 and current_md5 == saved_md5:
                    log(f"文件已存在且MD5匹配，跳过下载: {new_filename}", "INFO")
                    skipped_count += 1
                    continue
                else:
                    log(f"文件已存在但MD5不匹配，重新下载: {new_filename}", "INFO")
            except Exception as e:
                log(f"读取MD5文件失败，重新下载: {e}", "ERROR")
        else:
            log(f"文件已存在但无MD5文件，重新下载: {new_filename}", "INFO")
    else:
        log(f"文件不存在，开始下载: {new_filename}", "INFO")
    
    # 下载文件
    log(f"开始下载: {filename}", "INFO")
    try:
        response = requests.get(file_url, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        log(f"下载失败 - 文件: {filename}, 错误: {e}", "ERROR")
        continue
    
    # 保存文件（直接使用新文件名格式）
    with open(file_path, 'wb') as f:
        f.write(response.content)
    log(f"文件保存成功: {file_path}", "SUCCESS")
    downloaded_count += 1
    
    # 计算并保存MD5哈希（MD5文件名保持不变，使用原版本号）
    md5_value = save_md5_hash(file_path, version, is_fabric)
    if md5_value:
        log(f"MD5计算完成 - 文件: {new_filename}, MD5: {md5_value}", "INFO")
    else:
        log(f"无法计算下载文件的MD5: {new_filename}", "ERROR")

# 输出统计信息
log(f"处理完成，共发现 {link_count} 个资源包文件", "SUCCESS")
log(f"下载了 {downloaded_count} 个文件，跳过了 {skipped_count} 个文件", "INFO")
if skipped_count > 0:
    log(f"跳过的文件: {skipped_count} 个", "DETAIL")