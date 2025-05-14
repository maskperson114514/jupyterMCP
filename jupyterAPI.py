import os
import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

class JupyterAPI:
    def __init__(self, python_env_path: str = None, notebook_path: str = "work.ipynb", init_code: str = "",isnew: bool = True) -> None:
        """
        初始化JupyterAPI类
        
        参数:
            python_env_path (str): Python环境路径，默认为None表示使用当前环境
            init_code (str): 初始化代码，默认为空
            notebook_path (str): 笔记本文件路径，默认为"work.ipynb"
        """
        self.python_env_path = python_env_path
        self.notebook = None
        self.notebook_path = notebook_path
        self.client = None
        self.original_cells = None  # 保存原始单元格列表
        
        if isnew:
            if os.path.exists(self.notebook_path):
                os.remove(self.notebook_path)
        self.open_notebook(self.notebook_path)
        
        #初始化notebook 代码
        if init_code != "":
            self.insert_and_execute_cell(code = init_code, cell_type = 'code', index = 0)
        
    
    def open_notebook(self, path):
        """
        打开一个已存在的笔记本或创建新笔记本
        
        参数:
            path (str): 笔记本文件路径
        """
        
        # 如果当前已有打开的notebook且路径与新路径不同，先保存当前notebook
        if self.notebook is not None and self.notebook_path != path:
            self.save_notebook()
            
        self.notebook_path = path
        
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                self.notebook = nbformat.read(f, as_version=4)
            # 保存原始单元格
            self.original_cells = self.notebook.cells
        else:
            self.notebook = nbformat.v4.new_notebook()
            self.original_cells = []
            self.save_notebook()
            
        self.start_kernel()
        return self.notebook

    def initialize_notebook(self) -> NotebookClient:
        # 备份原始单元格（如果还没备份）
        if self.original_cells is None:
            self.original_cells = self.notebook.cells
            
        self.notebook.cells = []
        
        # 如果客户端已存在，先关闭
        if self.client:
            self.client = None
            
        # 重新创建客户端并初始化内核
        self.client = NotebookClient(self.notebook)
        self.client.execute(cleanup_kc=False)  # 执行空笔记本，确保内核就绪
        
        # 恢复原始单元格
        self.notebook.cells = self.original_cells
        return self.client
        
    def start_kernel(self) -> NotebookClient:
        """
        启动或重启内核
        
        返回:
            NotebookClient: 客户端实例
        """
        # 备份原始单元格（如果还没备份）
        if self.original_cells is None:
            self.original_cells = self.notebook.cells
            
        self.notebook.cells = []
        if self.client:
            # 如果存在客户端，尝试关闭内核
            try:
                self.client.km.shutdown_kernel()
            except:
                pass
            self.client = None
        
        # 创建新的客户端
        self.client = NotebookClient(self.notebook)
        self.client.execute(cleanup_kc=False)  # 执行空笔记本，确保内核就绪
        self.notebook.cells = self.original_cells
        return self.client
    
    def shutdown_kernel(self) -> None:
        """
        关闭内核
        """
        if self.client and hasattr(self.client, 'km'):
            try:
                self.client.km.shutdown_kernel()
                self.client = None
            except:
                pass
        
    def run_cell(self, cell_index: int) -> str | None:
        """
        执行特定索引的单元格，不影响其他单元格的执行状态
        
        参数:
            cell_index (int): 单元格索引
            
        返回:
            str: 执行成功时返回单元格输出文本，失败时返回错误信息
        """
        if self.notebook is None:
            raise ValueError("没有打开的笔记本")
            
        if cell_index < 0 or cell_index >= len(self.notebook.cells):
            raise ValueError(f"单元格索引超出范围: {cell_index}")
            
        cell = self.notebook.cells[cell_index]
        if cell.cell_type != 'code':
            raise ValueError(f"单元格不是代码类型: {cell_index}")
        
        # 确保客户端和内核已就绪
        if self.client is None:
            self.start_kernel()
        
        try:
            # 直接执行特定单元格
            self.client.execute_cell(cell, cell_index)
            self.save_notebook()
            # 执行成功，返回输出文本
            return self.get_cell_text_output(cell_index)
        except CellExecutionError as e:
            error_msg = f"单元格执行错误: {e}"
            print(error_msg)
            return error_msg
        except AssertionError:
            print("内核连接丢失，尝试重新启动内核...")
            self.start_kernel()
            try:
                self.client.execute_cell(cell, cell_index)
                self.save_notebook()
                # 重试成功，返回输出文本
                return self.get_cell_text_output(cell_index)
            except Exception as e:
                error_msg = f"重试执行单元格失败: {e}"
                print(error_msg)
                return error_msg
    
    def execute_cells_by_indices(self, indices: list[int]) -> dict:
        """
        按照提供的索引列表顺序执行特定单元格，遇到错误时停止执行
        
        参数:
            indices (list): 要执行的单元格索引列表
            
        返回:
            dict: 包含执行状态的字典，包括：
                  - success: 是否全部成功执行
                  - last_index: 最后执行的单元格索引
                  - error: 错误信息（如果有）
                  - warnings: 执行过程中的警告信息列表
                  - output: 最后执行单元格的输出（如果成功）
        """
        if self.notebook is None:
            raise ValueError("没有打开的笔记本")
        
        # 初始化内核
        if self.client is None:
            self.start_kernel()
        
        result = {
            "success": True,
            "last_index": None,
            "error": None,
            "warnings": [],
            "output": None
        }
        
        for idx in indices:
            try:
                if idx < 0 or idx >= len(self.notebook.cells):
                    result["success"] = False
                    result["error"] = f"单元格索引超出范围: {idx}"
                    break
                
                cell = self.notebook.cells[idx]
                if cell.cell_type != 'code':
                    continue  # 跳过非代码单元格
                
                self.client.execute_cell(cell, idx)
                result["last_index"] = idx
                
                # 检查输出中是否有警告信息
                if hasattr(cell, 'outputs'):
                    for output in cell.outputs:
                        if output.output_type == 'stream' and output.name == 'stderr':
                            result["warnings"].append({
                                "cell_index": idx,
                                "message": output.text
                            })
                
            except Exception as e:
                result["success"] = False
                result["error"] = f"执行单元格 {idx} 时出错: {e}"
                result["last_index"] = idx
                break
        
        self.save_notebook()
        
        # 获取最后执行单元格的输出（如果有）
        if result["last_index"] is not None:
            result["output"] = self.get_cell_text_output(result["last_index"])
        
        return result
    
    def save_notebook(self) -> str | None:
        """
        保存笔记本到文件
        
        返回:
            str | None: 成功时返回None，失败时返回错误信息
        """
        try:
            if self.notebook is None or self.notebook_path is None:
                return "没有打开的笔记本或路径未指定"
                
            with open(self.notebook_path, 'w', encoding='utf-8') as f:
                nbformat.write(self.notebook, f)
            return None
        except Exception as e:
            return f"保存笔记本时出错: {e}"
    
    def insert_and_execute_cell(self, code: str, cell_type: str = 'code', index: int = None) -> dict:
        """
        插入并执行一个单元格
        
        参数:
            code (str): 单元格代码内容
            cell_type (str): 单元格类型，默认为'code'
            index (int): 插入位置，默认为None表示末尾
            
        返回:
            dict: 执行结果
        """
        if self.notebook is None:
            raise ValueError("没有打开的笔记本")
            
        if self.client is None:
            self.start_kernel()
        
        # 创建新单元格
        if cell_type == 'code':
            cell = nbformat.v4.new_code_cell(code)
        elif cell_type == 'markdown':
            cell = nbformat.v4.new_markdown_cell(code)
        else:
            raise ValueError(f"不支持的单元格类型: {cell_type}")
        
        # 插入单元格
        if index is None:
            self.notebook.cells.append(cell)
            cell_index = len(self.notebook.cells) - 1
        else:
            self.notebook.cells.insert(index, cell)
            cell_index = index
        
        # 如果是代码单元格，执行它
        if cell_type == 'code':
            try:
                self.client.execute_cell(cell, cell_index)
            except CellExecutionError as e:
                print(f"单元格执行错误: {e}")
            except AssertionError:
                print("内核连接丢失，尝试重新启动内核...")
                self.start_kernel()
                try:
                    self.client.execute_cell(cell, cell_index)
                except Exception as e:
                    print(f"重试执行单元格失败: {e}")
        
        # 更新原始单元格列表
        self.original_cells = self.notebook.cells
        self.save_notebook()
        return cell
    
    def insert_cell(self, code: str, cell_type: str = 'code', index: int = None) -> str:
        """
        仅插入一个单元格，但不执行
        
        参数:
            code (str): 单元格代码内容
            cell_type (str): 单元格类型，默认为'code'，可选'markdown'
            index (int): 插入位置，默认为None表示末尾
            
        返回:
            str: 成功时返回单元格索引，失败时返回错误信息
        """
        try:
            if self.notebook is None:
                return "没有打开的笔记本"
            
            # 创建新单元格
            if cell_type == 'code':
                cell = nbformat.v4.new_code_cell(code)
            elif cell_type == 'markdown':
                cell = nbformat.v4.new_markdown_cell(code)
            else:
                return f"不支持的单元格类型: {cell_type}"
            
            # 插入单元格
            if index is None:
                self.notebook.cells.append(cell)
                cell_index = len(self.notebook.cells) - 1
            else:
                if index < 0 or index > len(self.notebook.cells):
                    return f"无效的索引位置: {index}"
                self.notebook.cells.insert(index, cell)
                cell_index = index
            
            # 更新原始单元格列表
            self.original_cells = self.notebook.cells
            save_result = self.save_notebook()
            if save_result:
                return str(save_result)
            
            return str(cell_index)
        except Exception as e:
            return f"插入单元格时出错: {e}"
    
    def get_cells_info(self) -> str:
        """
        获取所有单元格信息，以markdown格式呈现
        包括 索引，类型，源代码，部分输出
        返回:
            str: markdown格式的单元格信息
        """
        if self.notebook is None:
            raise ValueError("没有打开的笔记本")
        
        cells_info = []
        for i, cell in enumerate(self.notebook.cells):
            cell_info = {
                'index': i,
                'type': cell.cell_type,
                'source': cell.source
            }
            
            if cell.cell_type == 'code' and hasattr(cell, 'outputs'):
                cell_info['has_output'] = len(cell.outputs) > 0
                
                # 获取输出内容
                if cell_info['has_output']:
                    output_text = self.get_cell_text_output(i)
                    # 处理输出，显示前100字符和后100字符
                    if output_text and len(output_text) > 200:
                        cell_info['output'] = output_text[:100] + "..." + output_text[-100:]
                    else:
                        cell_info['output'] = output_text
                else:
                    cell_info['output'] = ""
            
            cells_info.append(cell_info)
            
        # 转换为markdown格式
        markdown = "## 单元格信息\n\n"
        for cell in cells_info:
            markdown += f"### 单元格 {cell['index']}\n\n"
            markdown += f"- **类型**: {cell['type']}\n"
            markdown += f"- **源代码**:\n\n```python\n{cell['source']}\n```\n\n"
            if cell['type'] == 'code':
                if cell.get('has_output', False):
                    markdown += f"- **输出**:\n\n```\n{cell.get('output', '')}\n```\n\n"
                else:
                    markdown += "- **输出**: 无\n\n"
            markdown += "---\n\n"
        
        return markdown
    
    def get_notebook_info(self) -> dict:
        """
        获取笔记本信息
        
        返回:
            dict: 笔记本信息，包含code_cells和markdown_cells的索引列表
        """
        if self.notebook is None:
            raise ValueError("没有打开的笔记本")
        
        code_cells = []
        markdown_cells = []
        
        for i, cell in enumerate(self.notebook.cells):
            if cell.cell_type == 'code':
                code_cells.append(i)
            elif cell.cell_type == 'markdown':
                markdown_cells.append(i)
        
        return {
            'code_cells': code_cells,
            'markdown_cells': markdown_cells
        }
    
    def run_all_cells(self) -> str | None:
        """
        顺序运行所有单元格
        
        返回:
            str | None: 成功时返回None，失败时返回错误信息
        """
        try:
            if self.notebook is None:
                return "没有打开的笔记本"
                
            if self.client is None:
                self.start_kernel()
            
            self.client.execute(self.notebook)
            save_result = self.save_notebook()
            if save_result:
                return save_result
            return None
        except CellExecutionError as e:
            error_msg = f"单元格执行错误: {e}"
            print(error_msg)
            return error_msg
        except AssertionError:
            print("内核连接丢失，尝试重新启动内核...")
            try:
                self.start_kernel()
                self.client.execute(self.notebook)
                save_result = self.save_notebook()
                if save_result:
                    return save_result
                return None
            except Exception as e:
                error_msg = f"重试执行单元格失败: {e}"
                print(error_msg)
                return error_msg
    
    
    def get_cell_text_output(self, cell_index: int, start_index: int = 0, length: int = 3000) -> str:
        """
        获取指定单元格的文本输出
        
        参数:
            cell_index (int): 单元格索引
            start_index (int): 文本输出的起始索引，默认为0
            length (int): 要获取的文本长度，默认为3000
            
        返回:
            str: 单元格文本输出
        """
        if self.notebook is None:
            raise ValueError("没有打开的笔记本")
        
        if cell_index < 0 or cell_index >= len(self.notebook.cells):
            raise ValueError(f"单元格索引超出范围: {cell_index}")
        
        cell = self.notebook.cells[cell_index]
        if cell.cell_type != 'code' or not hasattr(cell, 'outputs'):
            return ""
        
        text_output = ""
        for output in cell.outputs:
            if output.output_type == 'stream':
                text_output += output.text
            elif output.output_type == 'execute_result' and 'text/plain' in output.data:
                text_output += output.data['text/plain']
            elif output.output_type == 'display_data' and 'text/plain' in output.data:
                text_output += output.data['text/plain']
        
        full_length = len(text_output)
        
        # 处理起始索引和长度
        if start_index < 0:
            start_index = 0
        if start_index >= full_length:
            result = ""
        else:
            if length is None:
                result = text_output[start_index:]
            else:
                result = text_output[start_index:start_index + length]
        
        # 如果需要返回总长度信息
        return f"总长度: {full_length}\n{result}"
    
    def get_image_output(self, cell_index: int, format: str = 'png') -> str | None:#归档状态不修改
        """
        获取指定单元格的图像输出
        
        参数:
            cell_index (int): 单元格索引
            format (str): 图像格式，默认为'png'
            
        返回:
            str | None: 图像数据 (Base64编码) 或 None
        """
        if self.notebook is None:
            raise ValueError("没有打开的笔记本")
        
        if cell_index < 0 or cell_index >= len(self.notebook.cells):
            raise ValueError(f"单元格索引超出范围: {cell_index}")
        
        cell = self.notebook.cells[cell_index]
        if cell.cell_type != 'code' or not hasattr(cell, 'outputs'):
            return None
        
        for output in cell.outputs:
            mime_type = f'image/{format}'
            if output.output_type in ['execute_result', 'display_data'] and mime_type in output.data:
                return output.data[mime_type]
                
        return None
    
    def edit_cell_content(self, cell_index: int, new_content: str) -> str | None:
        """
        编辑单元格内容
        
        参数:
            cell_index (int): 单元格索引
            new_content (str): 新的单元格内容
            
        返回:
            str | None: 成功时返回None，失败时返回错误信息
        """
        try:
            if self.notebook is None:
                return "没有打开的笔记本"
            
            if cell_index < 0 or cell_index >= len(self.notebook.cells):
                return f"单元格索引超出范围: {cell_index}"
            
            cell = self.notebook.cells[cell_index]
            cell.source = new_content
            save_result = self.save_notebook()
            if save_result:
                return save_result
            return None
        except Exception as e:
            return f"编辑单元格内容时出错: {e}"
    
    def set_slideshow_type(self, cell_index: int, slide_type: str | None) -> str | None:
        """
        设置单元格的幻灯片类型
        
        参数:
            cell_index (int): 单元格索引
            slide_type (str | None): 幻灯片类型 ('slide', 'subslide', 'fragment', 'skip', 'notes', None)
            
        返回:
            str | None: 成功时返回None，失败时返回错误信息
        """
        try:
            if self.notebook is None:
                return "没有打开的笔记本"
            
            if cell_index < 0 or cell_index >= len(self.notebook.cells):
                return f"单元格索引超出范围: {cell_index}"
            
            valid_types = ['slide', 'subslide', 'fragment', 'skip', 'notes', None]
            if slide_type not in valid_types:
                return f"无效的幻灯片类型: {slide_type}，有效类型为: {', '.join([str(t) for t in valid_types])}"
            
            cell = self.notebook.cells[cell_index]
            
            # 确保单元格有元数据
            if not hasattr(cell, 'metadata'):
                cell.metadata = {}
            
            # 设置幻灯片类型
            if slide_type is None:
                if 'slideshow' in cell.metadata:
                    del cell.metadata['slideshow']
            else:
                if 'slideshow' not in cell.metadata:
                    cell.metadata['slideshow'] = {}
                cell.metadata['slideshow']['slide_type'] = slide_type
            
            save_result = self.save_notebook()
            if save_result:
                return save_result
            return None
        except Exception as e:
            return f"设置幻灯片类型时出错: {e}"
        
    def delete_cell(self, cell_index: int) -> str | None:
        """
        删除指定索引的单元格
        
        参数:
            cell_index (int): 要删除的单元格索引
        
        返回:
            str | None: 成功时返回None，失败时返回错误信息
        """
        try:
            if self.notebook is None:
                return "没有打开的笔记本"   
            if cell_index < 0 or cell_index >= len(self.notebook.cells):
                return f"单元格索引超出范围: {cell_index}"
            del self.notebook.cells[cell_index]
            return None
        except Exception as e:
            return f"删除单元格时出错: {e}"
    def __del__(self) -> None:
        """析构函数，确保关闭内核"""
        self.shutdown_kernel()

# 使用示例
if __name__ == "__main__":
    try:
        # 创建实例并打开文件
        api = JupyterAPI(notebook_path="测试.ipynb")
        
        # 1. 标准方法：插入并执行代码
        api.insert_and_execute_cell("print('你好，世界！')")

        # 2. test.py风格：执行特定单元格
        # 执行第1个和第2个单元格
        api.execute_cells_by_indices([1, 2,3])
        
        # 3. 保存执行结果到新文件
        api.save_executed_notebook("测试_executed.ipynb")

        # 4. 获取单元格信息
        cells = api.get_cells_info()
        print(cells)
        
        # 确保关闭内核
        api.shutdown_kernel()
    except Exception as e:
        print(f"发生错误: {e}")