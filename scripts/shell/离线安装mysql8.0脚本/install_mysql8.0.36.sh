#!/bin/bash
set -e

# 定义基础路径
BASE_URL="http://10.6.6.75/mysql8.0.36"
WORKDIR="/tmp/mysql8.0.36"
mkdir -p "$WORKDIR"
cd "$WORKDIR"

# 所需文件列表
FILES=(
  "mysql-8.0.36-1.el7.x86_64.rpm-bundle.tar"
  "mysql-community-client-plugins-8.0.36-1.el7.x86_64.rpm"
  "mysql-community-icu-data-files-8.0.36-1.el7.x86_64.rpm"
)

echo "🔽 下载所有必要文件..."
for file in "${FILES[@]}"; do
  if [ ! -f "$file" ]; then
    curl -O "$BASE_URL/$file"
  fi
done

echo "📦 解压 bundle 包..."
tar -xf mysql-8.0.36-1.el7.x86_64.rpm-bundle.tar

echo "🧹 移除旧的 mariadb 和 postfix（如有）..."
yum remove -y mariadb-libs postfix || true

echo "📦 安装 MySQL 8.0.36 所有组件..."
yum localinstall -y \
  mysql-community-common-8.0.36-1.el7.x86_64.rpm \
  mysql-community-libs-8.0.36-1.el7.x86_64.rpm \
  mysql-community-client-8.0.36-1.el7.x86_64.rpm \
  mysql-community-client-plugins-8.0.36-1.el7.x86_64.rpm \
  mysql-community-icu-data-files-8.0.36-1.el7.x86_64.rpm \
  mysql-community-server-8.0.36-1.el7.x86_64.rpm

echo "🚀 启动并设置开机启动 MySQL..."
systemctl start mysqld
systemctl enable mysqld

echo "🔐 获取初始 root 密码："
grep 'temporary password' /var/log/mysqld.log || echo "❗未找到密码，请手动检查 /var/log/mysqld.log"

echo "✅ MySQL 8.0.36 安装完成，请立即登录修改 root 密码。"
