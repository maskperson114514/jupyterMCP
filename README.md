# JupyterMCP

JupyterMCP，允许通过MCP（Model Control Protocol）接口远程控制和操作Jupyter笔记本。该项目提供了一个sse协议的MCP，使AI助手或其他应用程序能够以编程方式创建、编辑和执行Jupyter笔记本单元格。

## 功能特点

- 📝 创建和打开Jupyter笔记本
- ▶️ 执行单个或多个代码单元格
- ✏️ 插入和编辑单元格内容
- 🔎 获取笔记本结构和单元格信息
- 💾 保存笔记本状态
- 🗑️ 删除单元格
- 📊 获取代码执行结果和输出
- 🖼️ 设置幻灯片模式（用于演示）

## 安装说明

### 前提条件

- Python 3.10+
- Jupyter Notebook 或 JupyterLab

### 安装步骤

1. 克隆仓库：

```bash
git clone https://github.com/maskperson114514/jupyterMCP.git
cd jupyterMCP
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

## 使用方法

在客户端中配置MCP

```json
{
  "mcpServers": {
    "jupyterMCP": {
      "autoApprove": [
        "save_notebook",
        "get_cells_info",
        "insert_and_execute_cell",
        "run_cell",
        "edit_cell_content",
        "execute_cells_by_indices",
        "run_all_cells",
        "get_notebook_info",
        "get_cell_text_output",
        "set_slideshow_type"
      ],
      "timeout": 60,
      "url": "http://localhost:48080/sse",
      "transportType": "sse"
    }
  }
}
```

### 启动服务器

```bash
python jupyterMCP.py --host 127.0.0.1 --port 48080
```

参数说明：

- `--host`: 服务器绑定的主机地址（默认：127.0.0.1）
- `--port`: 服务器监听的端口（默认：48080）

## API功能说明

JupyterMCP提供以下主要工具函数：

| 功能 | 描述 |
|------|------|
| `open_notebook` | 打开或创建笔记本 |
| `run_cell` | 执行特定索引的单元格 |
| `execute_cells_by_indices` | 按序执行多个单元格 |
| `save_notebook` | 保存笔记本 |
| `insert_and_execute_cell` | 插入并执行新单元格 |
| `insert_cell` | 插入新单元格（不执行） |
| `get_cells_info` | 获取所有单元格信息 |
| `get_notebook_info` | 获取笔记本基本信息 |
| `run_all_cells` | 执行所有代码单元格 |
| `get_cell_text_output` | 获取单元格文本输出 |
| `edit_cell_content` | 编辑单元格内容 |
| `set_slideshow_type` | 设置单元格幻灯片类型 |
| `delete_cell` | 删除单元格 |
