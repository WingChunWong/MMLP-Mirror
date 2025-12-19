"""
Minecraft Mod Language Modpack 资源包下载器
核心功能：自动扫描、下载并校验资源包文件
===========================================
"""

import os
import re
import hashlib
import requests
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Callable
from dataclasses import dataclass, field
from enum import Enum
from contextlib import contextmanager
from bs4 import BeautifulSoup
from pathlib import Path

# ===================== 枚举定义 =====================

class LogLevel(Enum):
    """日志级别"""
    ERROR = "ERROR"
    SUCCESS = "SUCCESS"
    INFO = "INFO"
    DEBUG = "DEBUG"

class DownloadStatus(Enum):
    """下载状态"""
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"

# ===================== 配置类 =====================

@dataclass
class AppConfig:
    """应用程序配置参数"""
    base_url: str = "http://8.137.167.65:64684/"
    target_dir: str = "resource_pack"
    timeout: int = 30
    chunk_size: int = 4096
    max_retries: int = 2

# ===================== 异常类 =====================

class DownloadError(Exception):
    """下载相关异常的基类"""
    pass

class NetworkError(DownloadError):
    """网络异常"""
    pass

class FileError(DownloadError):
    """文件操作异常"""
    pass

class ValidationError(DownloadError):
    """数据验证异常"""
    pass

# ===================== 重试装饰器 =====================

def retry_operation(operation: Callable, max_retries: int = 2):
    """
    为网络操作提供重试机制的装饰器
    
    Args:
        operation: 需要重试的函数
        max_retries: 最大重试次数
        
    Returns:
        包装后的函数
    """
    def wrapper(*args, **kwargs):
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                return operation(*args, **kwargs)
            except (NetworkError, requests.exceptions.RequestException) as e:
                last_exception = e
                if attempt < max_retries - 1:
                    continue
        
        if last_exception:
            raise NetworkError(f"操作失败，已重试{max_retries}次")
    
    return wrapper

# ===================== 日志类 =====================

class Logger:
    """控制台日志输出管理器"""
    
    # ANSI颜色码映射
    COLOR_MAP = {
        LogLevel.ERROR: "\033[31m",    # 红色
        LogLevel.SUCCESS: "\033[32m",  # 绿色
        LogLevel.INFO: "\033[33m",     # 黄色
        LogLevel.DEBUG: "\033[34m",    # 蓝色
    }
    
    RESET = "\033[0m"  # 重置颜色
    
    def __init__(self, log_level: str = "INFO"):
        """
        初始化日志记录器
        
        Args:
            log_level: 日志输出级别
        """
        self.log_level = log_level
    
    def log(self, message: str, level: LogLevel = LogLevel.INFO):
        """
        输出格式化日志到控制台
        
        Args:
            message: 日志消息内容
            level: 日志级别
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = self.COLOR_MAP.get(level, self.COLOR_MAP[LogLevel.INFO])
        print(f"{color}[{timestamp}] [{level.value}] - {message}{self.RESET}")
    
    def error(self, message: str):
        """输出错误级别日志"""
        self.log(message, LogLevel.ERROR)
    
    def success(self, message: str):
        """输出成功级别日志"""
        self.log(message, LogLevel.SUCCESS)
    
    def info(self, message: str):
        """输出信息级别日志"""
        self.log(message, LogLevel.INFO)
    
    def debug(self, message: str):
        """输出调试级别日志"""
        self.log(message, LogLevel.DEBUG)

# ===================== 工具类 =====================

class MD5Utils:
    """MD5校验相关工具函数"""
    
    @staticmethod
    def calculate_file_md5(file_path: Path, chunk_size: int = 4096) -> Optional[str]:
        """
        计算文件的MD5哈希值
        
        Args:
            file_path: 文件路径对象
            chunk_size: 读取块大小
            
        Returns:
            文件的MD5哈希值(小写)，文件不存在或读取失败时返回None
            
        Raises:
            FileError: 文件读取异常
        """
        if not file_path.exists():
            return None
            
        md5_hash = hashlib.md5()
        
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    md5_hash.update(chunk)
            return md5_hash.hexdigest().lower()
        except Exception as e:
            raise FileError(f"计算文件MD5失败: {e}")
    
    @staticmethod
    def validate_md5_format(md5_hash: str) -> bool:
        """
        验证MD5字符串格式是否正确
        
        Args:
            md5_hash: 待验证的MD5字符串
            
        Returns:
            True表示格式正确，False表示格式错误
        """
        if not md5_hash:
            return False
        return bool(re.match(r'^[a-f0-9]{32}$', md5_hash.lower()))


class VersionParser:
    """版本号解析工具"""
    
    # 文件名正则表达式模式
    VERSION_PATTERN = r'Minecraft-Mod-Language-Modpack-(1-\d+(?:-\d+)?)(-Fabric)?\.zip'
    
    @staticmethod
    def parse_filename(filename: str) -> Tuple[Optional[str], bool]:
        """
        从文件名解析版本号和类型信息
        
        Args:
            filename: 文件名
            
        Returns:
            (版本号, 是否为Fabric版本)
            
        Raises:
            ValidationError: 文件名格式无法解析
        """
        # 1.12.2版本特殊处理
        if filename == "Minecraft-Mod-Language-Modpack.zip":
            return "1-12-2", False
        
        match = re.match(VersionParser.VERSION_PATTERN, filename)
        if not match:
            raise ValidationError(f"无法识别的文件名格式: {filename}")
        
        version = match.group(1)
        is_fabric = match.group(2) is not None
        return version, is_fabric
    
    @staticmethod
    def build_md5_filename(version: str, is_fabric: bool) -> str:
        """
        根据版本信息生成对应的MD5文件名
        
        Args:
            version: 版本号
            is_fabric: 是否为Fabric版本
            
        Returns:
            MD5文件名
        """
        if version == "1-12-2":
            return "1.12.2.md5"
        
        version_dot = version.replace('-', '.')
        suffix = "-fabric" if is_fabric else ""
        return f"{version_dot}{suffix}.md5"

# ===================== 网络管理器 =====================

class NetworkManager:
    """网络请求管理，负责HTTP通信"""
    
    def __init__(self, config: AppConfig, logger: Logger):
        """
        初始化网络管理器
        
        Args:
            config: 应用程序配置
            logger: 日志记录器
        """
        self.config = config
        self.logger = logger
        self.session = requests.Session()  # 复用连接提高性能
    
    @retry_operation
    def get_remote_md5(self, version: str, is_fabric: bool) -> Optional[str]:
        """
        从服务器获取指定版本的MD5校验值
        
        Args:
            version: 版本号
            is_fabric: 是否为Fabric版本
            
        Returns:
            服务器上的MD5哈希值，获取失败时返回None
            
        Raises:
            NetworkError: 网络请求失败
            ValidationError: MD5格式验证失败
        """
        md5_filename = VersionParser.build_md5_filename(version, is_fabric)
        md5_url = f"{self.config.base_url}{md5_filename}"
        
        try:
            response = self.session.get(md5_url, timeout=self.config.timeout)
            response.raise_for_status()  # 检查HTTP状态码
            
            remote_md5 = response.text.strip().lower()
            
            if MD5Utils.validate_md5_format(remote_md5):
                return remote_md5
            else:
                raise ValidationError(f"远程MD5格式无效: {remote_md5}")
                
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"获取远程MD5失败: {e}")
    
    @retry_operation
    def download_file(self, url: str, local_path: Path) -> bool:
        """
        下载文件到本地
        
        Args:
            url: 文件下载地址
            local_path: 本地保存路径
            
        Returns:
            下载成功返回True，失败返回False
            
        Raises:
            NetworkError: 网络请求失败
        """
        try:
            response = self.session.get(url, timeout=self.config.timeout)
            response.raise_for_status()
            
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            return True
            
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"下载失败: {e}")
    
    @retry_operation
    def fetch_file_list(self) -> Optional[BeautifulSoup]:
        """
        从服务器获取资源包文件列表
        
        Returns:
            解析后的HTML文档对象，获取失败时返回None
            
        Raises:
            NetworkError: 网络请求失败
        """
        try:
            response = self.session.get(self.config.base_url, timeout=self.config.timeout)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"连接服务器失败: {e}")

# ===================== 文件管理器 =====================

class FileManager:
    """文件系统操作管理器"""
    
    def __init__(self, config: AppConfig, logger: Logger):
        """
        初始化文件管理器
        
        Args:
            config: 应用程序配置
            logger: 日志记录器
        """
        self.config = config
        self.logger = logger
        self.target_dir = Path(config.target_dir)
    
    def setup_directories(self):
        """
        创建下载目标目录
        
        Raises:
            FileError: 目录创建失败
        """
        try:
            self.target_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise FileError(f"创建目录失败: {e}")
    
    def save_md5_file(self, version: str, is_fabric: bool, md5_hash: str) -> bool:
        """
        保存MD5校验文件到本地
        
        Args:
            version: 版本号
            is_fabric: 是否为Fabric版本
            md5_hash: MD5哈希值
            
        Returns:
            保存成功返回True，失败返回False
            
        Raises:
            FileError: 文件保存失败
        """
        try:
            md5_filename = VersionParser.build_md5_filename(version, is_fabric)
            md5_file = self.target_dir / md5_filename
            
            with open(md5_file, 'w') as f:
                f.write(md5_hash.lower())
            
            return True
            
        except Exception as e:
            raise FileError(f"保存MD5文件失败: {e}")

# ===================== 数据模型 =====================

@dataclass
class FileInfo:
    """文件信息数据模型"""
    filename: str      # 文件名
    url: str           # 下载地址
    local_path: Path   # 本地保存路径
    version: Optional[str] = None      # 版本号
    is_fabric: bool = False            # 是否为Fabric版本
    remote_md5: Optional[str] = None   # 服务器MD5哈希值

# ===================== 下载处理器 =====================

class DownloadProcessor:
    """文件下载处理核心逻辑"""
    
    def __init__(self, config: AppConfig, logger: Logger):
        """
        初始化下载处理器
        
        Args:
            config: 应用程序配置
            logger: 日志记录器
        """
        self.config = config
        self.logger = logger
        
        self.network = NetworkManager(config, logger)
        self.file_manager = FileManager(config, logger)
        self.version_parser = VersionParser()
    
    def process_all_files(self, soup: BeautifulSoup) -> Dict[str, int]:
        """
        处理网页中所有找到的资源包文件
        
        Args:
            soup: 解析后的HTML文档对象
            
        Returns:
            下载统计信息字典
        """
        stats = self._initialize_stats()
        
        for link in soup.find_all('a'):
            href = link.get('href')
            
            # 跳过非资源链接
            if not self._is_resource_link(href):
                continue
            
            # 处理单个链接
            self._process_single_link(href, stats)
        
        return stats
    
    def _initialize_stats(self) -> Dict[str, int]:
        """初始化统计信息字典"""
        return {
            "total": 0,
            "successful": 0,
            "skipped": 0,
            "failed": 0
        }
    
    def _is_resource_link(self, href: Optional[str]) -> bool:
        """
        检查链接是否为有效的资源包文件
        
        Args:
            href: 链接地址
            
        Returns:
            是有效资源包链接返回True
        """
        return bool(href and href.endswith('.zip') and 
                   self._is_resource_filename(href))
    
    def _is_resource_filename(self, href: str) -> bool:
        """
        检查文件名是否匹配资源包命名模式
        
        Args:
            href: 链接地址
            
        Returns:
            文件名符合资源包模式返回True
        """
        filename = href.split('/')[-1]
        return filename.startswith("Minecraft-Mod-Language-Modpack")
    
    def _process_single_link(self, href: str, stats: Dict[str, int]):
        """
        处理单个资源链接
        
        Args:
            href: 资源链接地址
            stats: 统计信息字典
        """
        stats["total"] += 1
        filename = href.split('/')[-1]
        
        try:
            # 创建文件信息对象并处理
            file_info = self._create_file_info(href, filename)
            result = self.process_single_file(file_info)
            self._update_stats_from_result(result, stats)
        except Exception as e:
            self._handle_processing_error(filename, e, stats)
    
    def _create_file_info(self, href: str, filename: str) -> FileInfo:
        """
        创建文件信息对象
        
        Args:
            href: 文件链接地址
            filename: 文件名
            
        Returns:
            文件信息对象
        """
        # 处理相对URL
        file_url = self._build_full_url(href)
        local_path = self.file_manager.target_dir / filename
        
        return FileInfo(
            filename=filename,
            url=file_url,
            local_path=local_path
        )
    
    def _build_full_url(self, href: str) -> str:
        """
        构建完整的文件URL
        
        Args:
            href: 原始链接
            
        Returns:
            完整的URL地址
        """
        return href if href.startswith('http') else f"{self.config.base_url}{href}"
    
    def _update_stats_from_result(self, result: str, stats: Dict[str, int]):
        """
        根据处理结果更新统计信息
        
        Args:
            result: 处理结果
            stats: 统计信息字典
        """
        result_mapping = {
            "downloaded": "successful",
            "skipped": "skipped",
            "failed": "failed"
        }
        
        if result in result_mapping:
            stats[result_mapping[result]] += 1
    
    def _handle_processing_error(self, filename: str, error: Exception, 
                               stats: Dict[str, int]):
        """
        处理文件处理过程中的异常
        
        Args:
            filename: 文件名
            error: 异常对象
            stats: 统计信息字典
        """
        self.logger.error(f"处理文件 {filename} 时出错: {error}")
        stats["failed"] += 1
    
    def _is_valid_resource_link(self, href: Optional[str]) -> bool:
        """
        检查链接是否为有效的资源包文件
        
        Args:
            href: 链接地址
            
        Returns:
            是有效资源包链接返回True
        """
        if not href or not href.endswith('.zip'):
            return False
        
        filename = href.split('/')[-1]
        return filename.startswith("Minecraft-Mod-Language-Modpack")
    
    def _create_file_info(self, href: str, filename: str) -> FileInfo:
        """
        创建文件信息对象
        
        Args:
            href: 文件链接地址
            filename: 文件名
            
        Returns:
            文件信息对象
        """
        file_url = href if href.startswith('http') else f"{self.config.base_url}{href}"
        local_path = self.file_manager.target_dir / filename
        
        return FileInfo(
            filename=filename,
            url=file_url,
            local_path=local_path
        )
    
    def process_single_file(self, file_info: FileInfo) -> str:
        """
        处理单个文件下载流程
        
        Args:
            file_info: 文件信息对象
            
        Returns:
            处理结果状态字符串
        """
        # 步骤1: 解析版本信息
        if not self._parse_file_version(file_info):
            return "failed"
        
        # 步骤2: 获取远程MD5校验值
        if not self._fetch_remote_md5(file_info):
            return "failed"
        
        # 步骤3: 检查是否需要下载
        if not self._should_download_file(file_info):
            self.logger.info(f"跳过已存在: {file_info.filename}")
            return "skipped"
        
        # 步骤4: 下载并验证文件
        if self._download_and_verify_file(file_info):
            return "downloaded"
        
        return "failed"
    
    def _parse_file_version(self, file_info: FileInfo) -> bool:
        """
        从文件名解析出版本信息
        
        Args:
            file_info: 文件信息对象
            
        Returns:
            解析成功返回True，失败返回False
        """
        try:
            version, is_fabric = self.version_parser.parse_filename(file_info.filename)
            file_info.version = version
            file_info.is_fabric = is_fabric
            return True
        except ValidationError as e:
            self.logger.error(str(e))
            return False
    
    def _fetch_remote_md5(self, file_info: FileInfo) -> bool:
        """
        从服务器获取文件MD5校验值
        
        Args:
            file_info: 文件信息对象
            
        Returns:
            获取成功返回True，失败返回False
        """
        try:
            remote_md5 = self.network.get_remote_md5(file_info.version, file_info.is_fabric)
            if remote_md5:
                file_info.remote_md5 = remote_md5
                return True
            return False
        except NetworkError as e:
            self.logger.error(str(e))
            return False
    
    def _should_download_file(self, file_info: FileInfo) -> bool:
        """
        判断文件是否需要下载
        
        Args:
            file_info: 文件信息对象
            
        Returns:
            需要下载返回True，否则返回False
        """
        # 检查1: 文件是否已存在
        if not file_info.local_path.exists():
            return True
        
        # 检查2: MD5是否匹配
        return self._is_md5_mismatch(file_info)
    
    def _is_md5_mismatch(self, file_info: FileInfo) -> bool:
        """
        检查本地文件与服务器MD5是否匹配
        
        Args:
            file_info: 文件信息对象
            
        Returns:
            不匹配返回True，匹配或无法检查返回False
        """
        local_md5 = MD5Utils.calculate_file_md5(file_info.local_path)
        
        # 无法计算本地MD5，需要重新下载
        if not local_md5:
            return True
        
        # MD5不匹配，需要重新下载
        if local_md5 != file_info.remote_md5:
            return True
        
        return False
    
    def _download_and_verify_file(self, file_info: FileInfo) -> bool:
        """
        下载文件并验证完整性
        
        Args:
            file_info: 文件信息对象
            
        Returns:
            下载验证成功返回True，失败返回False
        """
        self.logger.info(f"开始下载: {file_info.filename}")
        
        # 子步骤1: 下载文件
        if not self._download_file(file_info):
            return False
        
        # 子步骤2: 验证文件完整性
        if not self._verify_downloaded_file(file_info):
            return False
        
        # 子步骤3: 保存MD5校验文件
        return self._save_md5_file(file_info)
    
    def _download_file(self, file_info: FileInfo) -> bool:
        """
        执行文件下载
        
        Args:
            file_info: 文件信息对象
            
        Returns:
            下载成功返回True，失败返回False
        """
        try:
            self.network.download_file(file_info.url, file_info.local_path)
            return True
        except NetworkError as e:
            self.logger.error(str(e))
            return False
    
    def _verify_downloaded_file(self, file_info: FileInfo) -> bool:
        """
        验证下载文件的完整性
        
        Args:
            file_info: 文件信息对象
            
        Returns:
            验证通过返回True，失败返回False
        """
        local_md5 = MD5Utils.calculate_file_md5(file_info.local_path)
        if not local_md5:
            self.logger.error(f"无法计算文件MD5: {file_info.filename}")
            return False
        
        if local_md5 != file_info.remote_md5:
            self.logger.error(f"文件验证失败: {file_info.filename}")
            return False
        
        self.logger.success(f"下载完成: {file_info.filename}")
        return True
    
    def _save_md5_file(self, file_info: FileInfo) -> bool:
        """
        保存MD5校验文件
        
        Args:
            file_info: 文件信息对象
            
        Returns:
            保存成功返回True，失败返回False
        """
        try:
            self.file_manager.save_md5_file(
                file_info.version, 
                file_info.is_fabric, 
                file_info.remote_md5
            )
            return True
        except FileError as e:
            self.logger.error(str(e))
            return False

# ===================== 主程序类 =====================

class ResourcePackDownloader:
    """资源包下载器主入口"""
    
    def __init__(self, config: Optional[AppConfig] = None):
        """
        初始化下载器
        
        Args:
            config: 应用程序配置，不提供时使用默认配置
        """
        self.config = config or AppConfig()
        self.logger = Logger()
        
        # 初始化文件管理器
        self.file_manager = FileManager(self.config, self.logger)
        
        # 初始化下载处理器
        self.download_processor = DownloadProcessor(self.config, self.logger)
    
    def run(self):
        """主执行流程"""
        try:
            # 步骤1: 创建目标目录
            self.file_manager.setup_directories()
            
            # 步骤2: 获取文件列表
            soup = self.network_manager.fetch_file_list()
            if not soup:
                return
            
            # 步骤3: 处理所有文件
            stats = self.download_processor.process_all_files(soup)
            
            # 步骤4: 显示结果摘要
            self._show_simple_summary(stats)
            
        except Exception as e:
            self.logger.error(f"程序执行失败: {e}")
    
    @property
    def network_manager(self):
        """网络管理器延迟初始化属性"""
        if not hasattr(self, '_network_manager'):
            self._network_manager = NetworkManager(self.config, self.logger)
        return self._network_manager
    
    def _show_simple_summary(self, stats: Dict[str, int]):
        """
        显示执行结果摘要
        
        Args:
            stats: 下载统计信息
        """
        if stats["failed"] == 0:
            self.logger.success("所有文件处理完成")
        else:
            self.logger.info(f"处理完成，失败: {stats['failed']}个文件")

# ===================== 程序入口 =====================

def main() -> None:
    """程序主入口函数"""
    try:
        # 可在此处自定义配置
        config = AppConfig(
            target_dir="resource_pack",
            timeout=30
        )
        
        downloader = ResourcePackDownloader(config)
        downloader.run()
        
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"程序异常: {e}")

if __name__ == "__main__":
    main()