from typing import Any
from mcp.server.fastmcp import FastMCP, Image
from starlette.applications import Starlette
from mcp.server.sse import SseServerTransport
from starlette.requests import Request
from starlette.routing import Mount, Route
from mcp.server import Server
import uvicorn
import json # 导入json模块

from jupyterAPI import JupyterAPI

# Initialize FastMCP server (SSE)
mcp = FastMCP("jupyter-tool")

# 全局唯一的 JupyterAPI 实例
try:
    jupyter_api_instance = JupyterAPI(notebook_path="work.ipynb", isnew=True)
except Exception as e:
    print(f"Failed to initialize JupyterAPI: {e}")
    jupyter_api_instance = None

def format_error(tool_name: str, error: Exception) -> str:
    return f"### 工具 '{tool_name}' 执行错误\n\n**错误类型:** `{type(error).__name__}`\n\n**错误信息:**\n```\n{str(error)}\n```"

def format_success(tool_name: str, message: str, details: dict = None) -> str:
    md = f"### 工具 '{tool_name}' 执行成功\n\n**信息:** {message}\n\n"
    if details:
        md += "**详细信息:**\n"
        for key, value in details.items():
            md += f"- **{key.replace('_', ' ').capitalize()}**: `{value}`\n"
    return md

@mcp.tool()
async def open_notebook(notebook_path: str) -> str:
    """
    打开一个已存在的笔记本或创建一个新的笔记本。
    API实例后续将操作此笔记本。

    参数:
    - notebook_path (str): .ipynb 笔记本文件的路径。

    返回:
    - str: Markdown格式的执行结果。
           成功示例: "### 工具 'open_notebook' 执行成功\n\n**信息:** Notebook 'work.ipynb' opened/created and kernel started.\n\n"
           失败示例: "### 工具 'open_notebook' 执行错误\n\n**错误类型:** `ValueError`\n\n**错误信息:**\n```\nSome error message\n```"
    """
    tool_name = "open_notebook"
    if jupyter_api_instance is None:
        return format_error(tool_name, RuntimeError("JupyterAPI not initialized."))
    try:
        jupyter_api_instance.open_notebook(path=notebook_path)
        return format_success(tool_name, f"Notebook '{notebook_path}' opened/created and kernel started.")
    except Exception as e:
        return format_error(tool_name, e)

@mcp.tool()
async def run_cell(cell_index_str: str) -> str:
    """
    按索引执行当前笔记本中的特定代码单元格。

    参数:
    - cell_index_str (str): 单元格索引的字符串表示形式 (例如, "0", "1")。

    返回:
    - str: Markdown格式的执行结果，包含单元格输出或错误信息。
           成功示例: "### 工具 'run_cell' 执行成功\n\n**单元格索引:** `0`\n\n**输出:**\n```\nHello World\n```"
           无输出示例: "### 工具 'run_cell' 执行成功\n\n**单元格索引:** `1`\n\n**信息:** Cell executed, but no text output.\n\n"
           失败示例: "### 工具 'run_cell' 执行错误\n\n**错误类型:** `ValueError`\n\n**错误信息:**\n```\nCell index out of range\n```"
    """
    tool_name = "run_cell"
    if jupyter_api_instance is None:
        return format_error(tool_name, RuntimeError("JupyterAPI not initialized."))
    try:
        cell_index = int(cell_index_str)
        output = jupyter_api_instance.run_cell(cell_index)
        if output is None: # No text output but successful execution
             return format_success(tool_name, "Cell executed, but no text output.", details={"cell_index": cell_index})
        # Check if output is an error message from run_cell itself
        if "单元格执行错误:" in output or "内核连接丢失" in output or "重试执行单元格失败" in output:
             return format_success(tool_name, "Cell execution resulted in an error/warning.", details={"cell_index": cell_index, "details": output})

        return f"### 工具 '{tool_name}' 执行成功\n\n**单元格索引:** `{cell_index}`\n\n**输出:**\n```\n{output}\n```"
    except ValueError as ve:
        return format_error(tool_name, ve)
    except Exception as e:
        return format_error(tool_name, e)

@mcp.tool()
async def execute_cells_by_indices(indices_json_str: str) -> str:
    """
    按顺序执行当前笔记本中由索引指定的特定代码单元格列表。
    如果任何单元格发生错误，执行将停止。

    参数:
    - indices_json_str (str): 表示单元格索引列表（整数）的JSON字符串。
                              示例: "[0, 1, 3]"

    返回:
    - str: Markdown格式的执行结果。
    """
    tool_name = "execute_cells_by_indices"
    if jupyter_api_instance is None:
        return format_error(tool_name, RuntimeError("JupyterAPI not initialized."))
    try:
        indices = json.loads(indices_json_str)
        if not isinstance(indices, list) or not all(isinstance(i, int) for i in indices):
            raise ValueError("Input must be a JSON string of a list of integers.")
        
        result = jupyter_api_instance.execute_cells_by_indices(indices)
        
        md_output = f"### 工具 '{tool_name}' 执行结果\n\n"
        md_output += f"- **执行状态:** `{'成功' if result.get('success') else '失败'}`\n"
        if result.get('last_index') is not None:
            md_output += f"- **最后执行的单元格索引:** `{result['last_index']}`\n"
        
        if result.get('error'):
            md_output += f"- **错误信息:** `{result['error']}`\n"
            
        if result.get('warnings'):
            md_output += "- **警告信息:**\n"
            for warning in result['warnings']:
                md_output += f"  - 单元格 `{warning['cell_index']}`: {warning['message']}\n"
        
        if result.get('output'):
            md_output += f"- **最后执行单元格的输出:**\n```\n{result['output']}\n```\n"
        else:
            md_output += "- **最后执行单元格的输出:** `无`\n"
            
        return md_output

    except json.JSONDecodeError:
        return format_error(tool_name, ValueError("Invalid JSON format for indices."))
    except ValueError as ve:
        return format_error(tool_name, ve)
    except Exception as e:
        return format_error(tool_name, e)

@mcp.tool()
async def save_notebook() -> str:
    """
    将笔记本的当前状态保存到其文件。

    返回:
    - str: Markdown格式的执行结果。
    """
    tool_name = "save_notebook"
    if jupyter_api_instance is None:
        return format_error(tool_name, RuntimeError("JupyterAPI not initialized."))
    try:
        error_message = jupyter_api_instance.save_notebook()
        if error_message is None:
            return format_success(tool_name, "Notebook saved successfully.")
        else:
            return format_error(tool_name, RuntimeError(f"Error saving notebook: {error_message}"))
    except Exception as e:
        return format_error(tool_name, e)

@mcp.tool()
async def insert_and_execute_cell(code: str, cell_type: str = 'code', index_str: str = "None") -> str:
    """
    插入带有给定代码/内容的新单元格，如果是代码单元格则执行它，
    并保存笔记本。

    参数:
    - code (str): 新单元格的源代码或内容。
    - cell_type (str): 单元格的类型, 'code' 或 'markdown'。默认为 'code'。
    - index_str (str): 单元格应插入位置的索引的字符串表示。
                       "None" 或空字符串表示在末尾追加。例如："0", "1"。

    返回:
    - str: Markdown格式的执行结果，包含新单元格索引和输出（如果适用）。
    """
    tool_name = "insert_and_execute_cell"
    if jupyter_api_instance is None:
        return format_error(tool_name, RuntimeError("JupyterAPI not initialized."))
    try:
        actual_index_param = None
        if index_str.lower() != "none" and index_str != "":
            actual_index_param = int(index_str)
        
        # JupyterAPI.insert_and_execute_cell returns the cell object
        cell_obj = jupyter_api_instance.insert_and_execute_cell(
            code=code,
            cell_type=cell_type,
            index=actual_index_param
        )

        # Determine the actual index of the inserted cell
        # This logic might need refinement based on how JupyterAPI handles indices
        inserted_at_index = -1
        if actual_index_param is not None:
            inserted_at_index = actual_index_param
        else: # Appended
            inserted_at_index = len(jupyter_api_instance.notebook.cells) - 1
        
        md_output = f"### 工具 '{tool_name}' 执行成功\n\n"
        md_output += f"- **单元格类型:** `{cell_type}`\n"
        md_output += f"- **插入索引:** `{inserted_at_index}` (基于输入 `{index_str}`)\n"
        
        if cell_type == 'code':
            # Attempt to get output for the executed cell
            # Ensure index is valid before fetching output
            if 0 <= inserted_at_index < len(jupyter_api_instance.notebook.cells):
                output = jupyter_api_instance.get_cell_text_output(inserted_at_index)
                md_output += f"- **执行输出:**\n```\n{output if output else '无文本输出'}\n```\n"
            else:
                md_output += f"- **执行输出:** `无法在索引 {inserted_at_index} 获取输出 (单元格总数: {len(jupyter_api_instance.notebook.cells)})`\n"
        else:
            md_output += "- **执行输出:** `非代码单元格，未执行`\n"
            
        return md_output

    except ValueError as ve: # For int(index_str)
        return format_error(tool_name, ValueError(f"Invalid index format: {str(ve)}"))
    except Exception as e:
        return format_error(tool_name, e)

@mcp.tool()
async def insert_cell(code: str, cell_type: str = 'code', index_str: str = "None") -> str:
    """
    将带有给定代码/内容的新单元格插入笔记本，但不执行它。
    插入后会保存笔记本。

    参数:
    - code (str): 新单元格的源代码或内容。
    - cell_type (str): 单元格的类型, 'code' 或 'markdown'。默认为 'code'。
    - index_str (str): 单元格应插入位置的索引的字符串表示。
                       "None" 或空字符串表示在末尾追加。例如："0", "1"。

    返回:
    - str: Markdown格式的执行结果，包含新单元格的索引或错误信息。
    """
    tool_name = "insert_cell"
    if jupyter_api_instance is None:
        return format_error(tool_name, RuntimeError("JupyterAPI not initialized."))
    try:
        actual_index = None
        if index_str.lower() != "none" and index_str != "":
            actual_index = int(index_str)

        result_str = jupyter_api_instance.insert_cell(
            code=code,
            cell_type=cell_type,
            index=actual_index
        )
        # jupyterAPI.insert_cell returns index as str or error message
        try:
            # Check if result_str is an integer (index)
            returned_index = int(result_str)
            return format_success(tool_name, "Cell inserted successfully.", details={"cell_index": returned_index, "cell_type": cell_type})
        except ValueError:
            # If not an int, it's an error message from insert_cell
            return format_error(tool_name, RuntimeError(f"Failed to insert cell: {result_str}"))

    except ValueError as ve: # For int(index_str)
        return format_error(tool_name, ValueError(f"Invalid index format: {str(ve)}"))
    except Exception as e:
        return format_error(tool_name, e)

@mcp.tool()
async def get_cells_info() -> str:
    """
    检索当前笔记本中所有单元格的信息。
    信息包括索引、类型、源代码以及代码单元格输出的片段。

    返回:
    - str: 包含所有单元格信息的Markdown格式字符串。
           如果没有打开笔记本，则返回错误消息字符串。
    """
    tool_name = "get_cells_info"
    if jupyter_api_instance is None:
        return format_error(tool_name, RuntimeError("JupyterAPI not initialized."))
    try:
        # This function already returns Markdown
        info = jupyter_api_instance.get_cells_info()
        return f"### 工具 '{tool_name}' 执行成功\n\n{info}"
    except Exception as e:
        return format_error(tool_name, e)

@mcp.tool()
async def get_notebook_info() -> str:
    """
    检索有关当前笔记本的基本信息，包括代码单元格和markdown单元格的索引列表。

    返回:
    - str: Markdown格式的笔记本信息。
    """
    tool_name = "get_notebook_info"
    if jupyter_api_instance is None:
        return format_error(tool_name, RuntimeError("JupyterAPI not initialized."))
    try:
        info = jupyter_api_instance.get_notebook_info() # dict
        md_output = f"### 工具 '{tool_name}' 执行成功\n\n**笔记本信息:**\n"
        md_output += f"- **代码单元格索引:** `{info.get('code_cells', [])}`\n"
        md_output += f"- **Markdown单元格索引:** `{info.get('markdown_cells', [])}`\n"
        return md_output
    except Exception as e:
        return format_error(tool_name, e)

@mcp.tool()
async def run_all_cells() -> str:
    """
    按顺序执行当前笔记本中的所有代码单元格。
    执行后会保存笔记本。

    返回:
    - str: Markdown格式的执行结果。
    """
    tool_name = "run_all_cells"
    if jupyter_api_instance is None:
        return format_error(tool_name, RuntimeError("JupyterAPI not initialized."))
    try:
        error_message = jupyter_api_instance.run_all_cells()
        if error_message is None:
            return format_success(tool_name, "All cells executed successfully.")
        else:
            # Error message from run_all_cells might contain specifics
            return format_error(tool_name, RuntimeError(f"Cell execution error: {error_message}"))
    except Exception as e:
        return format_error(tool_name, e)

@mcp.tool()
async def get_cell_text_output(cell_index_str: str, start_index_str: str = "0", length_str: str = "3000") -> str:
    """
    检索特定代码单元格的文本输出。

    参数:
    - cell_index_str (str): 单元格索引的字符串表示 (例如, "0")。
    - start_index_str (str): 输出起始字符索引的字符串表示。默认为 "0"。
    - length_str (str): 要检索输出的最大长度的字符串表示。默认为 "3000"。

    返回:
    - str: Markdown格式的单元格文本输出或错误信息。
    """
    tool_name = "get_cell_text_output"
    if jupyter_api_instance is None:
        return format_error(tool_name, RuntimeError("JupyterAPI not initialized."))
    try:
        cell_index = int(cell_index_str)
        start_index = int(start_index_str)
        length = int(length_str)

        output = jupyter_api_instance.get_cell_text_output(
            cell_index=cell_index,
            start_index=start_index,
            length=length
        )
        # Output format is "总长度: {full_length}\n{result}" or "" or error
        if not output:
             return format_success(tool_name, "No text output for this cell.", details={"cell_index": cell_index})

        return f"### 工具 '{tool_name}' 执行成功\n\n**单元格索引:** `{cell_index}`\n**请求范围:** 起始 `{start_index}`, 长度 `{length}`\n\n**文本输出:**\n```\n{output}\n```"
    except ValueError as ve: # For int conversions
        return format_error(tool_name, ValueError(f"Invalid parameter format: {str(ve)}"))
    except Exception as e: # Catch errors from jupyter_api_instance.get_cell_text_output
        return format_error(tool_name, e)


# @mcp.tool()
# async def get_image_output(cell_index_str: str, image_format: str = 'png') -> str:
#     """
#     以Base64编码格式检索特定代码单元格的图像输出。

#     参数:
#     - cell_index_str (str): 单元格索引的字符串表示 (例如, "0")。
#     - image_format (str): 所需的图像格式 (例如, 'png', 'jpeg')。默认为 'png'。

#     返回:
#     - str: Markdown格式的结果，包含Base64编码的图像数据或错误/未找到信息。
#            成功示例: "### 工具 'get_image_output' 执行成功\n\n**单元格索引:** `0`\n**图像格式:** `png`\n\n**Base64图像数据:**\n```\nbase64_string...\n```"
#            未找到示例: "### 工具 'get_image_output' 执行提醒\n\n**信息:** No image output in 'png' format found for cell 0.\n\n"
#     """
#     tool_name = "get_image_output"
#     if jupyter_api_instance is None:
#         return format_error(tool_name, RuntimeError("JupyterAPI not initialized."))
#     try:
#         cell_index = int(cell_index_str)
#         image_data_base64 = jupyter_api_instance.get_image_output(
#             cell_index=cell_index,
#             format=image_format
#         )
#         if image_data_base64 is not None:
#             return f"### 工具 '{tool_name}' 执行成功\n\n**单元格索引:** `{cell_index}`\n**图像格式:** `{image_format}`\n\n**Base64图像数据:**\n```\n{image_data_base64}\n```"
#         else:
#             return f"### 工具 '{tool_name}' 执行提醒\n\n**信息:** No image output in '{image_format}' format found for cell {cell_index}.\n\n"
#     except ValueError as ve: # For int(cell_index_str)
#         return format_error(tool_name, ValueError(f"Invalid cell index format: {str(ve)}"))
#     except Exception as e:
#         return format_error(tool_name, e)

@mcp.tool()
async def edit_cell_content(cell_index_str: str, new_content: str) -> str:
    """
    编辑笔记本中现有单元格的源内容。
    编辑后会保存笔记本。

    参数:
    - cell_index_str (str): 要编辑单元格索引的字符串表示 (例如, "0")。
    - new_content (str): 单元格的新源内容(完整代码)。

    返回:
    - str: Markdown格式的执行结果。
    """
    tool_name = "edit_cell_content"
    if jupyter_api_instance is None:
        return format_error(tool_name, RuntimeError("JupyterAPI not initialized."))
    try:
        cell_index = int(cell_index_str)
        error_message = jupyter_api_instance.edit_cell_content(
            cell_index=cell_index,
            new_content=new_content
        )
        if error_message is None:
            return format_success(tool_name, f"Content of cell {cell_index} updated successfully.")
        else:
            return format_error(tool_name, RuntimeError(f"Error editing cell content: {error_message}"))
    except ValueError as ve: # For int(cell_index_str)
        return format_error(tool_name, ValueError(f"Invalid cell index format: {str(ve)}"))
    except Exception as e:
        return format_error(tool_name, e)

@mcp.tool()
async def set_slideshow_type(cell_index_str: str, slide_type_str: str) -> str:
    """
    在笔记本的元数据中为特定单元格设置幻灯片类型。
    设置类型后会保存笔记本。

    参数:
    - cell_index_str (str): 单元格索引的字符串表示 (例如, "0")。
    - slide_type_str (str): 幻灯片类型。有效值为 'slide', 'subslide',
                              'fragment', 'skip', 'notes'。要删除幻灯片类型，
                              传递 "None" 或空字符串。

    返回:
    - str: Markdown格式的执行结果。
    """
    tool_name = "set_slideshow_type"
    if jupyter_api_instance is None:
        return format_error(tool_name, RuntimeError("JupyterAPI not initialized."))
    try:
        cell_index = int(cell_index_str)
        
        actual_slide_type = None
        if slide_type_str.lower() == "none" or slide_type_str == "":
            actual_slide_type = None
        else:
            actual_slide_type = slide_type_str
            
        valid_types_for_check = ['slide', 'subslide', 'fragment', 'skip', 'notes']
        if actual_slide_type is not None and actual_slide_type not in valid_types_for_check:
             return format_error(tool_name, ValueError(f"Invalid slide_type: '{slide_type_str}'. Valid types are {valid_types_for_check} or 'None'/''.") )

        error_message = jupyter_api_instance.set_slideshow_type(
            cell_index=cell_index,
            slide_type=actual_slide_type
        )
        if error_message is None:
            return format_success(tool_name, f"Slideshow type for cell {cell_index} set to '{actual_slide_type}'.")
        else:
            return format_error(tool_name, RuntimeError(f"Error setting slideshow type: {error_message}"))
    except ValueError as ve: # For int(cell_index_str)
        return format_error(tool_name, ValueError(f"Invalid cell index format: {str(ve)}"))
    except Exception as e:
        return format_error(tool_name, e)

@mcp.tool()
async def delete_cell(cell_index_str: str) -> str:
    """
    从笔记本中按指定索引删除单元格。
    重要提示：此操作不会自动保存笔记本。
    如果希望持久化此更改，请之后调用 'save_notebook' 工具。

    参数:
    - cell_index_str (str): 要删除单元格索引的字符串表示 (例如, "0")。

    返回:
    - str: Markdown格式的执行结果。
    """
    tool_name = "delete_cell"
    if jupyter_api_instance is None:
        return format_error(tool_name, RuntimeError("JupyterAPI not initialized."))
    try:
        cell_index = int(cell_index_str)
        error_message = jupyter_api_instance.delete_cell(cell_index=cell_index)

        if error_message is None:
            return format_success(tool_name, f"Cell {cell_index} deleted. Notebook NOT saved automatically.")
        else:
            return format_error(tool_name, RuntimeError(f"Error deleting cell: {error_message}"))
    except ValueError as ve: # For int(cell_index_str)
        return format_error(tool_name, ValueError(f"Invalid cell index format: {str(ve)}"))
    except Exception as e:
        return format_error(tool_name, e)


def create_starlette_app(mcp_server: Server, *, debug: bool = False) -> Starlette:
    """Create a Starlette application that can server the provied mcp server with SSE."""
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        async with sse.connect_sse(
                request.scope,
                request.receive,
                request._send,  # noqa: SLF001
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )

    return Starlette(
        debug=debug,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )


if __name__ == "__main__":
    if jupyter_api_instance is None:
        print("JupyterAPI instance could not be created. MCP server might not function correctly.")
        # Decide if server should exit or run with degraded functionality
        # exit(1) # Optionally exit if API is critical

    mcp_server = mcp._mcp_server  # noqa: WPS437

    import argparse
    
    parser = argparse.ArgumentParser(description='Run MCP SSE-based server for Jupyter tools')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=48080, help='Port to listen on')
    args = parser.parse_args()

    starlette_app = create_starlette_app(mcp_server, debug=True)

    uvicorn.run(starlette_app, host=args.host, port=args.port)
