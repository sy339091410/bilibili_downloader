# B站视频下载器

## 功能特性
- 支持普通视频/番剧/短链下载
- 自动选择最高画质
- 无需额外依赖（Python标准库实现）
- 支持分辨率选择（1080P/4K/8K）

## 安装使用
```bash
# 直接运行（需Python3.6+）
python bilibili_downloader.py [视频URL]
```

## 参数说明
```
--quality       视频清晰度（数字代码，默认127=8K）
--output_dir    下载目录（默认当前目录）
--url           视频URL（支持命令行直接传入）
```

## 使用示例
```bash
# 下载4K视频到指定目录
python bilibili_downloader.py --quality 120 --output_dir ~/Videos https://www.bilibili.com/video/BV1xx411c7AX
```

## 注意事项
1. 请遵守B站用户协议和版权法规
2. 8K/4K画质需要大会员账号登录
3. 遇到解析失败时请检查URL格式

## 常见问题
Q: 提示"无法获取视频信息"
A: 请尝试更新Cookie或使用大会员账号

Q: 下载速度慢
A: 可尝试降低清晰度参数（如使用--quality 112）