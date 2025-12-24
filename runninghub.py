import http.client
import json
import mimetypes
from codecs import encode
import time
import os
import requests
API_HOST = "www.runninghub.cn"
API_KEY = "633f32f6f9f04d42a9e000e3ece8bc25"
WEB_APPID = "1973465795936260097"
#WEB_APPID = "2001838441669246977"
SysPrompt = """制作高质量动漫内容，  高帧率的动态感觉，非静态，顶级作画水平，中文动漫，无字幕，无背景音乐，自动运镜，合理特写，语音严格匹配口型，
不要出现文案对话外的语音，高质量的画面表现。日漫二次元画风。参考图不要出现在视频里的任何一帧，开局0.1秒就要切换镜头"""


def get_nodo(webappId,Api_Key):
    conn = http.client.HTTPSConnection(API_HOST)
    payload = ''
    headers = {}
    conn.request("GET", f"/api/webapp/apiCallDemo?apiKey={Api_Key}&webappId={webappId}", payload, headers)
    res = conn.getresponse()
    # 读取响应内容
    data = res.read()
    # 转成 Python 字典
    data_json = json.loads(data.decode("utf-8"))
    # 取出 nodeInfoList
    node_info_list = data_json.get("data", {}).get("nodeInfoList", [])
  
    #print("✅ 提取的 nodeInfoList:")
    #print(json.dumps(node_info_list, indent=2, ensure_ascii=False))
    return node_info_list


def upload_file(API_KEY, file_path):
    """
    上传文件到 RunningHub 平台
    """
    url = "https://www.runninghub.cn/task/openapi/upload"
    headers = {
        'Host': 'www.runninghub.cn'
    }
    data = {
        'apiKey': API_KEY,
        'fileType': 'input'
    }
    with open(file_path, 'rb') as f:
        files = {'file': f}
        response = requests.post(url, headers=headers, files=files, data=data)
    return response.json()

def input_Image(node_info_list,Api_key,file_path):
    #file_path = input(f"请输入您本地{target_node['fieldType']}文件路径: ").strip()
        #print("等待文件上传中")
    
    upload_result = upload_file(Api_key, file_path)
        #print("上传结果:", upload_result)
        # 假设 upload_file 已返回解析后的 JSON 字典
    imageNodeId = 0
    for nodeid in range(len(node_info_list)):
        if node_info_list[nodeid]['fieldType'] in ["IMAGE", "AUDIO", "VIDEO"]:
            imageNodeId = nodeid

            
    if upload_result and upload_result.get("msg") == "success":
        uploaded_file_name = upload_result.get("data", {}).get("fileName")
        if uploaded_file_name:
                node_info_list[imageNodeId]['fieldValue'] = uploaded_file_name
                print(f"✅ 已更新 {node_info_list[1]['fieldType']} fieldValue:", uploaded_file_name)
                return node_info_list
    else:
        print("❌ 上传失败或返回格式异常:", upload_result)
        return upload_result


def input_Prompt_Value(node_info_list,prompt):
    for nodeid in range(len(node_info_list)):
        if node_info_list[nodeid]['fieldName'] == 'text' or node_info_list[nodeid]['fieldName'] == 'prompt':
            node_info_list[nodeid]['fieldValue'] = prompt
    return node_info_list

def duration_seconds_change(node_info_list,duration_seconds):
    if duration_seconds == 10 or duration_seconds == 15:
        for nodeid in range(len(node_info_list)):
            if node_info_list[nodeid]['fieldName'] == 'duration_seconds':
                node_info_list[nodeid]['fieldValue'] = duration_seconds
        return node_info_list
    else:
        return node_info_list

def model_change(node_info_list,model_type):
    if model_type in ['portrait','landscape','portrait-hd','landscape-hd']:
        for nodeid in range(len(node_info_list)):
            if node_info_list[nodeid]['fieldName'] == 'model':
                node_info_list[nodeid]['fieldValue'] = model_type
                    #print(node_info_list[nodeid]['fieldData'])
                return node_info_list
    else:
        return node_info_list

# 1️⃣ 提交任务
def submit_task(webapp_id,API_KEY, node_info_list):
    #[{'nodeId': '1', 'nodeName': 'RH_Sora2_I2V', 'fieldName': 'duration_seconds', 'fieldValue': '10', 
    #       'fieldData': '[{"name":"10","index":"10","description":"","fastIndex":1.0},{"name":"15","index":"15","description":"","fastIndex":2.0}]', 
    #       'fieldType': 'LIST', 'description': 'duration_seconds', 'descriptionCn': None, 'descriptionEn': 'duration_seconds'}, 
    # {'nodeId': '1', 'nodeName': 'RH_Sora2_I2V', 'fieldName': 'model', 'fieldValue': 'portrait', 'fieldData': '
    #       [{"name":"portrait","index":"portrait","description":"","fastIndex":1.0},{"name":"landscape","index":"landscape",
    #       "description":"","fastIndex":2.0},{"name":"portrait-hd","index":"portrait-hd","description":"","fastIndex":3.0},
    #       {"name":"landscape-hd","index":"landscape-hd","description":"","fastIndex":4.0}]', 'fieldType': 'LIST', 'description': 'model', 
    #       'descriptionCn': None, 'descriptionEn': 'model'}, 
    # {'nodeId': '2', 'nodeName': 'LoadImage', 'fieldName': 'image', 
    #       'fieldValue': '825b8cb2f5603b068704ef435df77d570f081be814a40f652f080b8d4bc6ba03.png', 
    #       'fieldData': '[["example.png", "keep_this_dic"], {"image_upload": true}]', 'fieldType': 'IMAGE', 
    #       'description': 'image', 'descriptionCn': None, 'descriptionEn': 'image'}, 
    # {'nodeId': '15', 'nodeName': 'CR Text', 'fieldName': 'text', 
    #       'fieldValue': '提示词示例。', 'fieldData': '["STRING", {"default": "", "multiline": true}]', 
    #       'fieldType': 'STRING', 'description': 'text', 'descriptionCn': None, 'descriptionEn': 'text'}]
    print(node_info_list)
    conn = http.client.HTTPSConnection(API_HOST)
    payload = json.dumps({
        "webappId": webapp_id,
        "apiKey": API_KEY,
        # "quickCreateCode": quick_create_code,
        "nodeInfoList": node_info_list
    })
    headers = {
        'Host': API_HOST,
        'Content-Type': 'application/json'
    }
    conn.request("POST", "/task/openapi/ai-app/run", payload, headers)
    res = conn.getresponse()
    data = json.loads(res.read().decode("utf-8"))
    conn.close()

    if data.get("code") != 0:
        #ui抛出错误function
        print("❌ 提交任务失败:", data)
        exit()
    return data

def submit_task_all(webapp_id,API_KEY,file_path,SysPrompt,prompt='',duration_seconds=10,model_type='landscape'):
    """更新节点数据，提交所有任务"""

    #node_info_list = [{'nodeId': '1', 'nodeName': 'RH_Sora2_I2V', 'fieldName': 'duration_seconds', 'fieldValue': '10', 'fieldData': '[{"name":"10","index":"10","description":"","fastIndex":1.0},{"name":"15","index":"15","description":"","fastIndex":2.0}]', 'fieldType': 'LIST', 'description': 'duration_seconds', 'descriptionCn': None, 'descriptionEn': 'duration_seconds'}, {'nodeId': '1', 'nodeName': 'RH_Sora2_I2V', 'fieldName': 'model', 'fieldValue': 'landscape', 'fieldData': '[{"name":"portrait","index":"portrait","description":"","fastIndex":1.0},{"name":"landscape","index":"landscape","description":"","fastIndex":2.0},{"name":"portrait-hd","index":"portrait-hd","description":"","fastIndex":3.0},{"name":"landscape-hd","index":"landscape-hd","description":"","fastIndex":4.0}]', 'fieldType': 'LIST', 'description': 'model', 'descriptionCn': None, 'descriptionEn': 'model'}, {'nodeId': '2', 'nodeName': 'LoadImage', 'fieldName': 'image', 'fieldValue': '', 'fieldData': '[["example.png", "keep_this_dic"], {"image_upload": true}]', 'fieldType': 'IMAGE', 'description': 'image', 'descriptionCn': None, 'descriptionEn': 'image'}, {'nodeId': '15', 'nodeName': 'CR Text', 'fieldName': 'text', 'fieldValue': '提示词示例。', 'fieldData': '["STRING", {"default": "", "multiline": true}]', 'fieldType': 'STRING', 'description': 'text', 'descriptionCn': None, 'descriptionEn': 'text'}]
    node_info_list = get_nodo(webapp_id,API_KEY)
    # 更新节点数据
    node_info_list = input_Image(node_info_list,API_KEY,file_path)
    node_info_list = input_Prompt_Value(node_info_list, SysPrompt+prompt)
    node_info_list = model_change(node_info_list,model_type)
    node_info_list = duration_seconds_change(node_info_list,duration_seconds)
    return submit_task(webapp_id,API_KEY, node_info_list)


def query_task_outputs(task_id,API_KEY):
    #[{'fileUrl': 'https://rh-images.xiaoyaoyou.com/9eec455cb4bb5a3bfc09ac13dc2d1ce3/output/video/ComfyUI_00001_ujslh_1766042431.mp4', 
    # 'fileType': 'mp4', 'taskCostTime': '205', 'nodeId': '3', 'thirdPartyConsumeMoney': '0.000', 
    # 'consumeMoney': None, 'consumeCoins': '41'}]
    conn = http.client.HTTPSConnection(API_HOST)
    payload = json.dumps({
        "apiKey": API_KEY,
        "taskId": task_id
    })
    headers = {
        'Host': API_HOST,
        'Content-Type': 'application/json'
    }
    conn.request("POST", "/task/openapi/outputs", payload, headers)
    res = conn.getresponse()
    data = json.loads(res.read().decode("utf-8"))
    conn.close()
    return data

def download_result_file(file_url, save_path):
    """下载结果文件到本地"""
    
    
    response = requests.get(file_url, stream=True)
    
    with open(save_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    
    print(f"✅ 文件已下载到: {save_path}")



# node value update
#node_info_list = get_nodo(WEB_APPID,API_KEY)
#print(node_info_list)

#model_change(node_info_list,1)

#new_node_info_list = input_Image(node_info_list,API_KEY,"test2.png")

#promptALL = SysPrompt + testPrompt
#new_node_info_list_1 = input_Prompt_Value(new_node_info_list, promptALL)

#subimt_data = submit_task(WEB_APPID,API_KEY, new_node_info_list_1)

#print(subimt_data)

