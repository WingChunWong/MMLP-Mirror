import os
import re
import hashlib
import requests
from datetime import datetime
from bs4 import BeautifulSoup

# ===================== 日志模块 =====================

class LogColor:
    """
    终端日志颜色定义类
    
    提供ANSI转义序列来设置不同日志级别的颜色
    """
    RESET = "\033[0m"      # 重置颜色
    RED = "\033[31m"       # 错误级别 - 红色
    GREEN = "\033[32m"     # 成功级别 - 绿色
    YELLOW = "\033[33m"    # 信息级别 - 黄色
    BLUE = "\033[34m"      # 调试级别 - 蓝色
    CYAN = "\033[36m"      # 详情级别 - 青色

# 日志级别配置字典
# 格式: 级别名称: (颜色代码, 级别显示文本)
LOG_CONFIG = {
    "ERROR": (LogColor.RED, "ERROR"),
    "SUCCESS": (LogColor.GREEN, "SUCCESS"),
    "INFO": (LogColor.YELLOW, "INFO"),
    "DEBUG": (LogColor.BLUE, "DEBUG"),
    "DETAIL": (LogColor.CYAN, "DETAIL")
}

def log(message, level="INFO"):
    """
    输出带时间戳和颜色标记的格式化日志
    
    Args:
        message (str): 需要输出的日志消息
        level (str): 日志级别，可选值: ERROR/SUCCESS/INFO/DEBUG/DETAIL
                    默认为"INFO"
    """
    # 生成当前时间戳，格式: 年-月-日 时:分:秒
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 获取日志级别对应的颜色和显示文本，默认为INFO级别
    color, level_name = LOG_CONFIG.get(level.upper(), (LogColor.YELLOW, "INFO"))
    
    # 输出带颜色格式的日志行
    print(f"{color}[{timestamp}] [{level_name}] - {message}{LogColor.RESET}")

def calculate_file_md5(file_path):
    """
    计算本地文件的MD5校验值
    
    使用4096字节的块读取大文件，避免内存占用过高
    
    Args:
        file_path (str): 需要计算MD5的文件路径
        
    Returns:
        str: 文件的32位小写MD5哈希值
        None: 文件不存在或计算失败时返回None
    """
    # 创建MD5哈希对象
    md5_hash = hashlib.md5()
    
    try:
        # 以二进制读取模式打开文件
        with open(file_path, "rb") as f:
            # 使用迭代器分块读取文件，每块4096字节
            # 当读取到空字节时停止迭代
            for chunk in iter(lambda: f.read(4096), b""):
                md5_hash.update(chunk)
        
        # 返回32位小写十六进制哈希值
        return md5_hash.hexdigest().lower()
    
    except FileNotFoundError:
        # 文件不存在时静默返回None，由调用方处理
        return None
    
    except Exception as e:
        # 其他读取或计算错误记录日志
        log(f"计算文件MD5失败: {e}", "ERROR")
        return None

def get_remote_md5(version, is_fabric):
    """
    从远程服务器获取指定版本资源包的MD5校验文件
    
    支持两种命名规则:
    1. 1.12.2版本: 使用固定文件名"1.12.2.md5"
    2. 其他版本: 使用"版本号.md5"或"版本号-fabric.md5"格式
    
    Args:
        version (str): 资源包版本号，格式如"1-19-2"
        is_fabric (bool): 是否为Fabric版本的资源包
        
    Returns:
        str: 远程MD5哈希值(32位小写十六进制)
        None: 获取失败或格式无效时返回None
    """
    # 特殊处理Minecraft 1.12.2版本
    if version == "1-12-2":
        # 1.12.2版本MD5文件固定命名
        md5_filename = "1.12.2.md5"
        log("检测到1.12.2版本，使用固定MD5文件名", "DETAIL")
    else:
        # 通用版本命名规则: 将版本号中的横线替换为点号
        # 示例: "1-19-2" -> "1.19.2"
        version_for_md5 = version.replace('-', '.')
        
        # Fabric版本添加"-fabric"后缀
        md5_filename = f"{version_for_md5}-fabric.md5" if is_fabric else f"{version_for_md5}.md5"
    
    # 构建完整的远程MD5文件URL
    md5_url = f"{BASE_URL}{md5_filename}"
    
    try:
        log(f"请求远程MD5文件: {md5_url}", "DEBUG")
        
        # 发送HTTP GET请求获取MD5文件，设置30秒超时
        response = requests.get(md5_url, timeout=30)
        
        # 检查HTTP响应状态码，非200状态码会抛出异常
        response.raise_for_status()
        
        # 提取MD5值并去除两端空白字符，转换为小写
        remote_md5 = response.text.strip().lower()
        
        # 使用正则表达式验证MD5格式(32位十六进制)
        if re.match(r'^[a-f0-9]{32}$', remote_md5):
            # 显示前16位MD5值(避免日志过长)
            log(f"成功获取远程MD5: {remote_md5[:16]}...", "SUCCESS")
            return remote_md5
        else:
            # MD5格式不符合预期
            log(f"远程MD5格式无效(应为32位十六进制): {remote_md5}", "ERROR")
            return None
    
    except requests.exceptions.RequestException as e:
        # 处理网络请求相关错误
        log(f"获取远程MD5失败: {e}", "ERROR")
        return None

def save_md5_file(version, is_fabric, md5_hash):
    """
    将MD5哈希值保存到本地文件
    
    保存的文件与资源包在同一目录下，便于后续校验
    
    Args:
        version (str): 资源包版本号
        is_fabric (bool): 是否为Fabric版本
        md5_hash (str): 要保存的MD5哈希值
        
    Returns:
        bool: 保存成功返回True，失败返回False
    """
    # 命名规则与get_remote_md5函数保持一致
    if version == "1-12-2":
        # 1.12.2版本使用固定文件名
        md5_filename = "1.12.2.md5"
    else:
        # 通用版本命名规则
        version_for_md5 = version.replace('-', '.')
        md5_filename = f"{version_for_md5}-fabric.md5" if is_fabric else f"{version_for_md5}.md5"
    
    # 构建本地MD5文件完整路径
    md5_file = os.path.join(TARGET_DIR, md5_filename)
    
    try:
        # 以写入模式打开文件，保存小写形式的MD5值
        with open(md5_file, 'w') as f:
            f.write(md5_hash.lower())
        
        log(f"MD5文件已保存到: {md5_file}", "SUCCESS")
        return True
    
    except Exception as e:
        # 文件保存失败(权限不足、磁盘空间不够等)
        log(f"保存MD5文件失败: {e}", "ERROR")
        return False

def parse_filename(filename):
    """
    解析资源包文件名，提取版本信息和类型
    
    支持两种文件名格式:
    1. 1.12.2版本: "Minecraft-Mod-Language-Modpack.zip"
    2. 其他版本: "Minecraft-Mod-Language-Modpack-1-xx-x(-Fabric).zip"
    
    Args:
        filename (str): 资源包文件名
        
    Returns:
        tuple: (version, is_fabric) 版本号字符串和是否为Fabric版本
               (None, None): 文件名格式无法识别时返回
    """
    # 特殊处理Minecraft 1.12.2版本
    # 该版本使用固定文件名，无版本号后缀
    if filename == "Minecraft-Mod-Language-Modpack.zip":
        log("检测到1.12.2版本的特殊命名格式", "DETAIL")
        return "1-12-2", False
    
    # 其他版本的命名规则正则表达式
    # 匹配模式: Minecraft-Mod-Language-Modpack-1-xx(-x)?(-Fabric)?.zip
    # 解释:
    #   (1-\d+(?:-\d+)?) - 匹配版本号如1-19或1-19-2
    #   (-Fabric)?       - 可选的Fabric标识
    pattern = r'Minecraft-Mod-Language-Modpack-(1-\d+(?:-\d+)?)(-Fabric)?\.zip'
    match = re.match(pattern, filename)
    
    if not match:
        # 文件名不符合任何已知格式
        log(f"无法识别的文件名格式: {filename}", "ERROR")
        return None, None
    
    # 提取正则匹配的组
    version = match.group(1)          # 版本号部分
    is_fabric = match.group(2) is not None  # 判断是否有Fabric标识
    
    return version, is_fabric

# ===================== 主程序配置 =====================

# 远程服务器基础URL(包含资源包和MD5文件)
BASE_URL = "http://8.137.167.65:64684/"

# 本地资源包存储目录
TARGET_DIR = "resource_pack"

# ===================== 主程序执行流程 =====================

def main():
    """
    资源包下载器主函数
    
    执行流程:
    1. 创建本地存储目录
    2. 获取远程文件列表页面
    3. 解析页面中的所有资源包链接
    4. 逐个检查并下载需要的资源包
    5. 使用MD5校验文件完整性
    6. 输出下载统计信息
    """
    # 创建资源包存储目录(如果不存在)
    # exist_ok=True避免目录已存在时报错
    os.makedirs(TARGET_DIR, exist_ok=True)
    log(f"资源包存储目录: {os.path.abspath(TARGET_DIR)}", "INFO")
    
    # 下载统计计数器初始化
    link_count = 0      # 发现的资源包链接总数
    skipped_count = 0   # 跳过的文件数(MD5校验通过)
    downloaded_count = 0  # 实际下载的文件数
    
    # 步骤1: 获取远程文件列表页面
    log("正在连接服务器获取资源包列表...", "INFO")
    try:
        # 请求资源包列表页面，设置30秒超时
        response = requests.get(BASE_URL, timeout=30)
        
        # 检查HTTP响应状态，非200状态码会抛出异常
        response.raise_for_status()
        
        # 使用BeautifulSoup解析HTML页面
        soup = BeautifulSoup(response.text, 'html.parser')
        log("服务器连接成功，开始解析资源包列表", "SUCCESS")
    
    except requests.exceptions.RequestException as e:
        # 网络连接失败，程序无法继续执行
        log(f"连接服务器失败: {e}", "ERROR")
        log("请检查网络连接和服务器地址是否正确", "INFO")
        exit(1)  # 退出程序，返回错误码1
    
    # 步骤2: 遍历页面中的所有链接
    log("开始扫描页面中的资源包链接...", "INFO")
    for link in soup.find_all('a'):
        # 获取链接的href属性
        href = link.get('href')
        
        # 过滤非zip文件的链接
        if not href or not href.endswith('.zip'):
            continue
        
        # 提取文件名(去除路径部分)
        filename = href.split('/')[-1]
        
        # 只处理Minecraft语言资源包相关的文件
        if not filename.startswith("Minecraft-Mod-Language-Modpack"):
            continue
        
        # 计数器递增
        link_count += 1
        log(f"发现资源包文件 #{link_count}: {filename}", "DEBUG")
        
        # 步骤3: 解析文件名获取版本信息
        version, is_fabric = parse_filename(filename)
        
        # 文件名格式无法识别时跳过
        if not version:
            continue
        
        log(f"文件解析完成 - 版本: {version}, 类型: {'Fabric' if is_fabric else 'Forge'}", "DETAIL")
        
        # 构建完整的文件下载URL
        # 处理相对路径和绝对路径两种情况
        file_url = href if href.startswith('http') else f"{BASE_URL}{href}"
        
        # 构建本地文件保存路径
        file_path = os.path.join(TARGET_DIR, filename)
        
        # 步骤4: 获取远程MD5校验值
        log(f"正在获取文件校验信息...", "INFO")
        remote_md5 = get_remote_md5(version, is_fabric)
        
        if not remote_md5:
            # 无法获取MD5校验信息，跳过此文件
            log(f"跳过文件(无法获取校验信息): {filename}", "ERROR")
            continue
        
        # 步骤5: 检查本地文件状态并决定是否下载
        if os.path.exists(file_path):
            # 文件已存在，计算本地MD5进行比较
            log(f"本地文件已存在，进行MD5校验...", "INFO")
            local_md5 = calculate_file_md5(file_path)
            
            if local_md5:
                # MD5校验通过，文件无需重新下载
                if local_md5.lower() == remote_md5.lower():
                    log(f"文件校验通过，跳过下载: {filename}", "INFO")
                    log(f"校验码: 本地({local_md5[:16]}...) = 远程({remote_md5[:16]}...)", "DETAIL")
                    
                    # 更新本地MD5文件(确保版本最新)
                    save_md5_file(version, is_fabric, remote_md5)
                    skipped_count += 1
                    continue
                else:
                    # MD5不匹配，需要重新下载
                    log(f"文件已损坏或版本过旧，重新下载: {filename}", "WARNING")
                    log(f"校验码不匹配: 本地({local_md5[:16]}...) ≠ 远程({remote_md5[:16]}...)", "DETAIL")
            else:
                # 无法计算本地文件MD5，重新下载
                log(f"本地文件无法读取，重新下载: {filename}", "WARNING")
        else:
            # 文件不存在，需要下载
            log(f"本地文件不存在，开始下载: {filename}", "INFO")
        
        # 步骤6: 下载文件
        log(f"开始下载文件: {filename}", "INFO")
        try:
            # 发送HTTP请求下载文件
            response = requests.get(file_url, timeout=30)
            response.raise_for_status()
            
        except requests.exceptions.RequestException as e:
            # 下载失败，记录错误并继续处理下一个文件
            log(f"下载失败: {filename}, 错误: {e}", "ERROR")
            continue
        
        # 步骤7: 保存下载的文件
        try:
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            downloaded_count += 1
            log(f"文件保存成功: {file_path}", "SUCCESS")
            
        except IOError as e:
            # 文件保存失败(磁盘空间、权限等问题)
            log(f"文件保存失败: {filename}, 错误: {e}", "ERROR")
            continue
        
        # 步骤8: 验证下载文件的完整性
        log(f"开始验证下载文件的完整性...", "INFO")
        file_md5 = calculate_file_md5(file_path)
        
        if file_md5:
            if file_md5.lower() == remote_md5.lower():
                log(f"文件完整性验证通过: {filename}", "SUCCESS")
                log(f"计算校验码: {file_md5[:16]}...", "DETAIL")
                
                # 保存MD5校验文件到本地
                save_md5_file(version, is_fabric, remote_md5)
            else:
                # 下载的文件损坏
                log(f"文件完整性验证失败: {filename}", "ERROR")
                log(f"校验码不匹配: 计算值({file_md5[:16]}...) ≠ 期望值({remote_md5[:16]}...)", "DETAIL")
        else:
            log(f"无法计算下载文件的MD5: {filename}", "ERROR")
    
    # 步骤9: 输出最终统计信息
    print("\n" + "="*50)
    log("资源包下载任务完成", "SUCCESS")
    log(f"发现资源包链接: {link_count} 个", "INFO")
    log(f"下载新文件: {downloaded_count} 个", "INFO")
    log(f"跳过已存在文件: {skipped_count} 个", "INFO")
    
    print("="*50)

# 程序入口点
if __name__ == "__main__":
    main()
    log("程序执行完成", "INFO")