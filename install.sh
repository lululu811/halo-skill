#!/bin/bash
# HALO Skill 一键安装脚本
# 用法: curl -sL <url>/install.sh | bash

set -e

SKILL_DIR="${HOME}/.claude/skills/halo-skill"
REPO_URL="${1:-https://github.com/lululu811/halo-skill.git}"

echo ""
echo "🔷 HALO Skill 安装器"
echo "===================="
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 需要 Python 3.9+，请先安装"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✅ Python ${PYTHON_VERSION}"

# 检查 Claude Code skills 目录
SKILLS_BASE="${HOME}/.claude/skills"
if [ ! -d "${SKILLS_BASE}" ]; then
    echo "📁 创建 skills 目录: ${SKILLS_BASE}"
    mkdir -p "${SKILLS_BASE}"
fi

# 克隆或更新
if [ -d "${SKILL_DIR}" ]; then
    echo "📦 更新已有安装..."
    cd "${SKILL_DIR}"
    git pull
else
    echo "📦 克隆到 ${SKILL_DIR}..."
    git clone "${REPO_URL}" "${SKILL_DIR}"
fi

# 创建虚拟环境
cd "${SKILL_DIR}"
if [ ! -d ".venv" ]; then
    echo "🐍 创建虚拟环境..."
    python3 -m venv .venv
fi

# 激活并安装依赖
source .venv/bin/activate
echo "📚 安装依赖..."
pip install -q requests

# 验证
echo ""
echo "🔍 验证安装..."
if python3 -c "import requests; print('  requests ✅')"; then
    echo ""
    echo "✅ 安装成功！"
    echo ""
    echo "使用方法："
    echo "  在 Claude Code 中输入: /halo 600519"
    echo "  或自然语言: 帮我分析贵州茅台"
    echo ""
    echo "快速测试："
    echo "  cd ${SKILL_DIR}"
    echo "  source .venv/bin/activate"
    echo "  python test_data.py 600519 贵州茅台"
    echo ""
else
    echo "❌ 依赖安装失败"
    exit 1
fi
