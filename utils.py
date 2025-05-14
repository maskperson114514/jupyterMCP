from json import loads






def parse_jupyter_api(text):
    result = {"method": "", "params": {}}
    current_param = None
    current_value = []
    
    lines = text.splitlines()
    for line in lines:
        if line.startswith("$method:"):
            # 遇到新方法，保存上一个参数（如果有）
            if current_param is not None:
                result["params"][current_param] = _convert_value(current_value)
                current_value = []
            result["method"] = line[len("$method:"):].strip()
            current_param = None
        elif line.startswith("$pram:"):
            # 遇到新参数，保存上一个参数的值
            if current_param is not None:
                result["params"][current_param] = _convert_value(current_value)
                current_value = []
            current_param = line[len("$pram:"):].strip()
        else:
            # 收集参数值
            if current_param is not None:
                current_value.append(line)
    
    # 保存最后一个参数
    if current_param is not None:
        result["params"][current_param] = _convert_value(current_value)
    
    convert_params(result["params"], type_map)
    if result["method"] == "insert_and_execute_cell":
        try:
            if len(result["params"]["code"].splitlines()) > 20:
                return result, True
            else:
                return result, False
        except:pass
    return result, False

def _convert_value(lines):
    """将多行文本转换为字符串，处理 'None' -> None"""
    value = "\n".join(lines).strip()
    return None if value == "None" else value

def convert_params(params, type_map):
    """根据 type_map 将参数字典解析为指定类型，枚举默认取第一个"""
    for param, value in params.items():
        if param not in type_map:
            params[param] = value
            continue
        
        type_def = type_map[param]
        
        # 处理枚举类型（列表）
        if isinstance(type_def, list):
            if value in type_def:
                params[param] = value
            else:
                # 默认取枚举第一个
                params[param] = type_def[0] if type_def else None
        
        # 处理类型转换（如 str/int）
        else:
            if value is None:
                continue
            if type_def == int:
                # 尝试转换字符串或处理 None
                
                try:
                    params[param] = int(value)
                except (ValueError, TypeError):
                    print(f"转换错误: {value} 不能转换为 int")
                    return False
            elif type_def == list:
                try:
                    params[param] = loads(value.replace("'", '"').replace("None", "null"))
                except (ValueError, TypeError):
                    print(f"转换错误: {value} 不能转换为 list")
                    return False
            else:
                params[param] = value  # 其他类型可扩展
    
    return True

def call_method_from_dict(obj, method_dict):
    """通过字典动态调用对象的方法"""
    method_name = method_dict["method"]
    params = method_dict.get("params", {})

    # 1. 检查方法是否存在
    if not hasattr(obj, method_name):
        return f"对象中不存在方法: {method_name}"

    # 2. 获取方法引用
    method = getattr(obj, method_name)

    # 3. 调用方法并传参（自动解包字典）
    try:
        result = method(**params)
        if result is None:
            return "success"
        else:
            return result
    except TypeError as e:
        # 参数不匹配时的详细报错
        return f"调用 {method_name} 时参数错误: {str(e)}\n需要参数: {method.__code__.co_varnames[:method.__code__.co_argcount]}"

def paser_block(type: str, content: str) -> str:
    """解析代码块"""
    start_marker = f'```{type}\n'
    start_idx = content.find(start_marker)
    if start_idx == -1:
        return ''
    start_code = start_idx + len(start_marker)
    end_idx = content.find('```', start_code)
    return content[start_code:end_idx] if end_idx != -1 else ''

