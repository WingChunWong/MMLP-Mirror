# Minecraft 模组汉化资源包仓库

## 仓库信息
- **最后更新时间**: 2025-12-28 16:17:41 UTC+8
- **自动更新频率**: 每48小时
- **资源包数量**: 9 个
- **支持版本**: 1.12.2, 1.16.x, 1.18.x, 1.19.x, 1.20.x, 1.21.x

## 目录结构

```
MMLP-Mirror/
├── crawler.py                    # 爬虫脚本
├── LICENSE                       # 许可证文件
├── README.md                     # 项目说明文档
├── README_TEMPLATE.md            # README模板
├── .github/
│   └── workflows/
│       └── crawler.yml           # GitHub Actions 工作流配置
└── resource_pack/                # Minecraft 资源包目录
    ├── *.md5                     # 各版本MD5校验文件
    └── *.zip                     # 各版本资源包压缩文件
```

## 使用说明
1. 下载对应版本的资源包
2. 放入 Minecraft 的 resourcepacks 文件夹
3. 在游戏中启用

## 文件说明
- 文件名格式: `Minecraft-Mod-Language-Package-版本-fabric.zip` (Fabric版本)
- 文件名格式: `Minecraft-Mod-Language-Package-版本.zip` (Neo/Forge版本)

---

> 本仓库由 GitHub Actions 自动维护
