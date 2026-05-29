# MySQL 8.0.36 Offline Auto-Installation Script | MySQL 8.0.36 自动安装脚本使用说明

## Overview | 简介

This script performs a fully automated **offline installation** of MySQL 8.0.36 on CentOS 7. No manual download or extraction of RPM files is required — dependencies and common conflicts are handled automatically. Suitable for data center and intranet batch deployment scenarios.

本脚本可实现 MySQL 8.0.36 在 CentOS 7 环境下的**全自动离线安装**。无需手动下载和解压 rpm 文件，自动处理依赖与常见冲突。适用于数据中心、内网批量快速部署场景。

---

## Prerequisites | 准备条件

1. **Ensure the server can access the intranet file source | 确保服务器能访问内网文件源：**
   `http://10.6.6.6/mysql8.0.36/`
   The following files must be present | 目录下已上传：
   - `install_mysql8.0.36.sh`
   - `mysql-8.0.36-1.el7.x86_64.rpm-bundle.tar`
   - `mysql-community-client-plugins-8.0.36-1.el7.x86_64.rpm`
   - `mysql-community-icu-data-files-8.0.36-1.el7.x86_64.rpm`

2. **Target OS | 目标主机操作系统：**
   CentOS 7 / RHEL 7 / compatible el7 distributions

3. **Root privileges required | 具有 root 权限**

---

## Usage | 使用方法

1. **Download the script to the server | 下载脚本到服务器任意目录**（如 `/tmp`）

   ```bash
   cd /tmp
   curl -O http://10.6.6.6/mysql8.0.36/install_mysql8.0.36.sh
   ```

2. **Grant execute permission | 赋予脚本执行权限**

   ```bash
   chmod +x install_mysql8.0.36.sh
   ```

3. **Run the script | 执行脚本**

   ```bash
   ./install_mysql8.0.36.sh
   ```

   The script will automatically | 脚本会自动：
   - Download all required packages | 下载所需安装包
   - Extract the RPM bundle | 解压 rpm-bundle
   - Remove conflicting packages (e.g., mariadb-libs, postfix) | 卸载冲突包（如 mariadb-libs、postfix）
   - Install all MySQL 8.0.36 RPMs | 批量安装 MySQL 8.0.36 相关 rpm
   - Start MySQL and enable auto-start on boot | 启动 MySQL 并设置开机自启
   - Print the root temporary password | 输出 root 初始临时密码
