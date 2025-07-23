# MySQL 8.0.36 自动安装脚本使用说明

## 简介

本脚本可实现 MySQL 8.0.36 在 CentOS 7 环境下的**全自动离线安装**。无需手动下载和解压 rpm 文件，自动处理依赖与常见冲突。适用于数据中心、内网批量快速部署场景。

---

## 一、准备条件

1. **确保服务器能访问内网文件源：**
   `http://10.6.6.6/mysql8.0.36/`
   目录下已上传：

   * `install_mysql8.0.36.sh`
   * `mysql-8.0.36-1.el7.x86_64.rpm-bundle.tar`
   * `mysql-community-client-plugins-8.0.36-1.el7.x86_64.rpm`
   * `mysql-community-icu-data-files-8.0.36-1.el7.x86_64.rpm`

2. **目标主机操作系统：**

   * CentOS 7 / RHEL 7 / 兼容的 el7 发行版

3. **具有 root 权限**

---

## 二、使用方法

1. **下载脚本到服务器任意目录**（如 `/tmp`）

   ```bash
   cd /tmp
   curl -O http://10.6.6.6/mysql8.0.36/install_mysql8.0.36.sh
   ```

2. **赋予脚本执行权限**

   ```bash
   chmod +x install_mysql8.0.36.sh
   ```

3. **执行脚本**

   ```bash
   ./install_mysql8.0.36.sh
   ```

   > 脚本会自动：
   >
   > * 下载所需安装包
   > * 解压 rpm-bundle
   > * 卸载冲突包（如 mariadb-libs、postfix）
   > * 批量安装 MySQL 8.0.36 相关 rpm
   > * 启动 MySQL 并设置开机自启
   > * 输出 root 初始临时密码
