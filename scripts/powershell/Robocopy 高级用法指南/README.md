# Robocopy Advanced Usage Guide | Robocopy 高级用法指南

## Introduction | 简介

**Robocopy** (Robust File Copy) is a built-in Windows command-line tool that supports resume-on-failure, permission sync, multi-threading, and more. It is ideal for large-scale data migration, backup, and directory synchronization.

**Robocopy**（Robust File Copy）是 Windows 自带的命令行文件复制工具，支持断点续传、权限同步、多线程等高级特性，是大规模数据迁移、备份、目录同步的利器。

---

## Basic Usage | 基本用法

```bash
robocopy <source> <destination> [file] [options]
```

Example | 示例：
```bash
robocopy D:\data \\backup-server\backupshare /E /Z
```
Copies all files from `D:\data` to the backup share with resume support.
复制 D:\data 下所有文件到 \\backup-server\backupshare，支持断点续传。

---

## Common Parameters | 常用参数说明

| Parameter | Description | 说明 |
|-----------|-------------|------|
| /E | Copy all subdirectories (including empty ones) | 复制所有子目录（包括空目录） |
| /Z | Resume mode | 断点续传模式 |
| /MT[:N] | Multi-thread (max 128) | 多线程（N为线程数，最大128）|
| /MIR | Mirror source to destination | 镜像源目录到目标 |
| /LOG:file | Output log to file | 输出日志到文件 |
| /R:N | Retry count on error | 出错时重试次数 |
| /W:N | Wait seconds between retries | 每次重试间隔秒数 |
| /XO | Skip older files | 跳过旧文件 |
| /XD dir | Exclude directories | 排除指定目录 |
| /XF file | Exclude files | 排除指定文件 |
| /COPY:DATSOU | Copy all file attributes and permissions | 复制所有文件属性及权限 |

---

## Advanced Examples | 高级实战示例

### 1. Multi-thread for large files | 多线程加速复制大文件

```bash
robocopy D:\data \\backup-server\backupshare /E /MT:32
```

### 2. Resume + copy only new files | 断点续传+仅复制新文件

```bash
robocopy D:\data \\backup-server\backupshare /E /Z /XO
```

### 3. Mirror sync (use with caution) | 镜像同步（谨慎使用）

```bash
robocopy D:\data \\backup-server\backupshare /MIR /MT:16
```

### 4. Log + retry on error | 日志记录+错误重试

```bash
robocopy D:\data \\backup-server\backupshare /E /LOG:D:\robocopy.log /R:5 /W:10
```

### 5. Exclude files and directories | 排除部分文件和目录

```bash
robocopy D:\data \\backup-server\backupshare /E /XD temp logs /XF *.tmp *.bak
```

---

## FAQ | 常见问题

**Q1: Which OS is supported?**
A: Windows Vista and above (including Server). `robocopy.exe` ships in System32.
**Q1:** 支持哪些系统？
A：Windows Vista 及以上（含 Server），System32 目录自带。

**Q2: How to enable resume?**
A: Add the `/Z` flag.
**Q2:** 如何实现断点续传？
A：加 `/Z` 参数。

**Q3: Can it sync file permissions?**
A: Yes, use `/COPY:DATSOU` or `/SEC`.
**Q3:** 能否同步文件权限？
A：用 `/COPY:DATSOU` 或 `/SEC`。

**Q4: Can it run on a schedule?**
A: Yes, combine with Windows Task Scheduler.
**Q4:** 可以做定时自动备份吗？
A：可以，结合 Windows 任务计划程序。

---

## References | 参考资料

- [Official Docs (Microsoft)](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/robocopy)
- [Robocopy Manual](https://ss64.com/nt/robocopy.html)

---

## License

MIT License
