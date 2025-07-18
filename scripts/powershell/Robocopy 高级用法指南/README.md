
# Robocopy 高级用法指南

## 简介

**Robocopy**（Robust File Copy）是 Windows 自带的命令行文件复制工具，支持断点续传、权限同步、多线程等高级特性，是大规模数据迁移、备份、目录同步的利器。无论是日常备份、数据灾备，还是批量文件同步，Robocopy 都能胜任。

---

## 基本用法

```bash
robocopy <源路径> <目标路径> [文件名] [选项]
```

示例：  
```bash
robocopy D:\data \\backup-server\backupshare /E /Z
```
- 复制 D:\data 下所有文件到 \\backup-server\backupshare，支持断点续传。

---

## 常用参数说明

| 参数         | 含义                        |
|--------------|-----------------------------|
| /E           | 复制所有子目录（包括空目录） |
| /Z           | 断点续传模式                |
| /MT[:N]      | 多线程（N为线程数，最大128）|
| /MIR         | 镜像源目录到目标            |
| /LOG:文件    | 输出日志到文件              |
| /R:次数      | 出错时重试次数              |
| /W:秒数      | 每次重试间隔秒数            |
| /XO          | 跳过旧文件                  |
| /XD 目录     | 排除指定目录                |
| /XF 文件     | 排除指定文件                |
| /COPY:DATSOU | 复制所有文件属性及权限      |

---

## 高级实战示例

### 1. 多线程加速复制大文件

```bash
robocopy D:\data \\backup-server\backupshare /E /MT:32
```

### 2. 断点续传+仅复制新文件

```bash
robocopy D:\data \\backup-server\backupshare /E /Z /XO
```

### 3. 镜像同步（完全一致，谨慎使用）

```bash
robocopy D:\data \\backup-server\backupshare /MIR /MT:16
```

### 4. 日志记录+错误重试

```bash
robocopy D:\data \\backup-server\backupshare /E /LOG:D:\robocopy.log /R:5 /W:10
```

### 5. 排除部分文件和目录

```bash
robocopy D:\data \\backup-server\backupshare /E /XD temp logs /XF *.tmp *.bak
```

---

## 常见问题（FAQ）

**Q1:** Robocopy 支持哪些系统？  
**A:** Windows Vista 及以上（含 Server），System32 目录自带 robocopy.exe。

**Q2:** 如何实现断点续传？  
**A:** 加 `/Z` 参数。

**Q3:** 能否同步文件权限？  
**A:** 用 `/COPY:DATSOU` 或 `/SEC`。

**Q4:** 可以做定时自动备份吗？  
**A:** 可以，结合 Windows 任务计划程序。

---

## 参考资料

- [官方文档（微软）](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/robocopy)
- [Robocopy 使用手册（中文）](https://ss64.com/nt/robocopy.html)

---

## License

MIT License

---

欢迎补充和交流！
