import json
import os
import threading
import requests
import time


DEFAULT_MOTIONS = {
    "凝视推进": "slow, emotional push-in, focus intensifies on the subject's expression",
    "探索摇移": "smooth cinematic pan, revealing the extended scene",
    "悬停环绕": "slow orbiting shot around the central subject, 3/4 view",
    "呼吸感浮动": "subtle handheld breathing effect, very slow and natural camera drift",
    "升降揭示": "smooth crane movement, perspective shifts vertically",
    "关键帧顿挫": "animatic rhythm, slight holds on key poses, hand-drawn feel",
    "残影爆发": "smear frames action start, dynamic motion blur with afterimages",
    "震屏冲击": "impact frame with strong screen shake",
    "缩放冲击": "anime-style quick zoom, with a slight screen jerk for emphasis",
    "背景流线": "speed lines background effect, environment blurs into motion lines",
    "风动万物": "unified wind effect, hair, clothing, and foliage swaying in sync",
    "能量脉动": "pulsing glow effect, with light particles emanating rhythmically",
    "特写镜头": "tight close-up, framing subject from shoulders up, emphasizing facial expressions and emotions",
    "极端特写镜头": "extreme close-up, filling frame with small detail like eyes, lips, or hands, creating intense intimacy",
    "正反打镜头": "shot-reverse shot pattern, alternating between two characters in conversation, maintaining eye line match",
    "过肩镜头": "over-the-shoulder shot, camera positioned behind one character looking at another, establishing spatial relationship",
    "低角度仰拍": "extreme low angle shot, looking up at subject from ground level, exaggerating height and power",
    "俯冲贴地": "rapid low-altitude drone shot, camera skimming the ground surface",
    "镜头变焦": "zoom shot, changing focal length to bring subject closer or further without moving camera",
    "环绕运镜": "360-degree orbiting shot, camera circling around subject while maintaining constant distance",
    "升降镜头": "crane shot, vertical camera movement rising or descending while maintaining level framing",
    "移轴镜头": "tilt-shift lens effect, miniature-like appearance with selective focus and altered perspective"
}# --- core_logic.py ---

MOTION_LIBRARY =[
  {
    "name": "特写镜头",
    "mode": "景别控制",
    "short_prompt": "close-up framing",
    "prompt": "tight close-up, framing subject from shoulders up, emphasizing facial expressions and emotions",
    "tags": ["表情", "情感", "细节", "专注", "人物内心"]
  },
  {
    "name": "凝视推进",
    "mode": "推镜头 (靠近)",
    "short_prompt": "slow push-in",
    "prompt": "slow, emotional push-in, focus intensifies on the subject's expression",
    "tags": ["靠近", "情感", "特写", "缓慢", "焦点", "放大", "聚焦", "内心"]
  },
  {
    "name": "极端特写镜头",
    "mode": "景别控制",
    "short_prompt": "extreme close-up",
    "prompt": "extreme close-up, filling frame with small detail like eyes, lips, or hands, creating intense intimacy",
    "tags": ["亲密", "细节", "放大", "冲击力", "微观世界"]
  },
  {
    "name": "探索摇移",
    "mode": "横摇/平移",
    "short_prompt": "cinematic pan",
    "prompt": "smooth cinematic pan, revealing the extended scene",
    "tags": ["平移", "全景", "寻找", "环境", "展开", "左右", "风景", "过场"]
  },
  {
    "name": "悬停环绕",
    "mode": "环绕镜头",
    "short_prompt": "orbiting shot",
    "prompt": "slow orbiting shot around the central subject, 3/4 view, cinematic lighting",
    "tags": ["转圈", "立体", "全方位", "高光", "英雄时刻", "环绕"]
  },
  {
    "name": "呼吸感浮动",
    "mode": "手持感 (微动)",
    "short_prompt": "handheld drift",
    "prompt": "subtle handheld breathing effect, very slow and natural camera drift",
    "tags": ["真实", "日常", "手持", "呼吸", "生活化", "自然", "漂浮"]
  },
  {
    "name": "升降揭示",
    "mode": "摇臂升降",
    "short_prompt": "crane up/down",
    "prompt": "smooth crane movement, perspective shifts vertically from low to high",
    "tags": ["上升", "俯瞰", "揭开", "壮观", "垂直", "宏大", "高度"]
  },
  {
    "name": "关键帧顿挫",
    "mode": "动画节奏",
    "short_prompt": "animatic hold",
    "prompt": "animatic rhythm, slight holds on key poses, hand-drawn feel",
    "tags": ["卡顿", "张力", "二次元", "节奏", "动作", "有力", "动漫", "力量"]
  },
  {
    "name": "残影爆发",
    "mode": "视觉特效",
    "short_prompt": "smear action",
    "prompt": "smear frames action start, dynamic motion blur with afterimages",
    "tags": ["速度", "瞬移", "挥刀", "出拳", "快", "爆发", "幻影", "攻击"]
  },
  {
    "name": "震屏冲击",
    "mode": "屏幕震动",
    "short_prompt": "screen shake",
    "prompt": "impact frame with strong screen shake, followed by quick stabilization",
    "tags": ["爆炸", "打击", "怒吼", "震撼", "力量", "碰撞", "落地", "震动"]
  },
  {
    "name": "缩放冲击",
    "mode": "快速拉近",
    "short_prompt": "quick zoom",
    "prompt": "anime-style quick zoom, with a slight screen jerk for emphasis",
    "tags": ["惊讶", "发现", "锁定", "突然", "瞪眼", "注目", "拉近", "特写"]
  },
  {
    "name": "背景流线",
    "mode": "背景模糊",
    "short_prompt": "speed lines",
    "prompt": "speed lines background effect, environment blurs into motion lines",
    "tags": ["飞行", "奔跑", "冲刺", "速度线", "快", "运动", "竞速", "赶路"]
  },
  {
    "name": "正反打镜头",
    "mode": "对话拍摄",
    "short_prompt": "shot-reverse shot",
    "prompt": "shot-reverse shot pattern, alternating between two characters in conversation",
    "tags": ["对话", "互动", "电影语言", "视线匹配", "节奏感"]
  },
  {
    "name": "过肩镜头",
    "mode": "对话拍摄",
    "short_prompt": "over-the-shoulder",
    "prompt": "over-the-shoulder shot, camera positioned behind one character",
    "tags": ["空间关系", "对话", "连接感", "标准镜头", "人物互动"]
  },
  {
    "name": "低角度仰拍",
    "mode": "特殊角度",
    "short_prompt": "low angle upshot",
    "prompt": "extreme low angle shot, looking up at subject from ground level",
    "tags": ["威严", "英雄感", "压迫", "仰视", "夸张透视"]
  },
  {
    "name": "俯冲贴地",
    "mode": "低空掠过",
    "short_prompt": "low-altitude skim",
    "prompt": "rapid low-altitude drone shot, camera skimming the ground surface",
    "tags": ["低空", "飞行", "惊险", "视角", "极速", "贴地", "俯冲"]
  },
  {
    "name": "移轴镜头",
    "mode": "特殊效果",
    "short_prompt": "tilt-shift effect",
    "prompt": "tilt-shift lens effect, miniature-like appearance with selective focus",
    "tags": ["微缩模型", "特殊焦点", "创意效果", "透视调整", "艺术感"]
  }
]
class VideoDownloader:
    @staticmethod
    def download(url, save_path, filename):
        """执行物理下载，将视频保存到指定目录"""
        if not os.path.exists(save_path):
            os.makedirs(save_path)
        
        full_path = os.path.join(save_path, filename)
        
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            with open(full_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return full_path
        except Exception as e:
            print(f"下载失败: {e}")
            return None
        
        

class KeyEntity:
    """每个 API Key 的实体，记录并发限制及冷却状态"""
    def __init__(self, api_key, limit, label="Key"):
        self.api_key = api_key
        self.label = label
        self.limit = int(limit)
        self.current_active = 0
        self.cooldown_until = 0  # 冷却截止时间戳
        self.lock = threading.Lock()

    def is_available(self, blacklist):
        """检查 Key 是否可用：不在黑名单、并发未满、不在冷却中"""
        if self.api_key in blacklist:
            return False
        with self.lock:
            return self.current_active < self.limit and time.time() >= self.cooldown_until

class ResourceManager:
    def __init__(self, parent_app, api_config_list):
        self.app = parent_app  # 用于读取 self.app.stop_queue_signal
        self.cv = threading.Condition() # 核心调度广播器
        self.key_entities = []
        self.update_pool(api_config_list)

    def update_pool(self, config_list):
        """当用户在 UI 修改 Key 池后，同步更新内存实体"""
        with self.cv:
            self.key_entities = [
                KeyEntity(c['key'], c['limit'], c.get('label', f"Key-{i}")) 
                for i, c in enumerate(config_list)
            ]
            self.cv.notify_all() 

    def acquire_key(self, blacklist):
        """
        核心调度方法：
        1. 阻塞排队。
        2. 如果检测到全局 stop_queue_signal，立即返回 None。
        3. 否则返回可用的 Key 信息字典。
        """
        with self.cv:
            while True:
                # --- 逃生门：检测到停止信号，立即退出排队 ---
                if getattr(self.app, 'stop_queue_signal', False):
                    return None

                # 寻找当前最优可用 Key
                for entity in self.key_entities:
                    if entity.is_available(blacklist):
                        with entity.lock:
                            entity.current_active += 1
                        # 返回一个方便 work 函数使用的字典
                        return {
                            'key': entity.api_key,
                            'label': entity.label,
                            'entity': entity # 方便 release 时引用
                        }
                
                # 如果暂时没有可用 Key，在此挂起
                # 设置 1 秒超时是为了能定期醒来检查 stop_queue_signal 和冷却状态
                self.cv.wait(timeout=1.0)

    def release_key(self, api_key, fail_code=None):
        """
        任务 return 0 或 805 后释放资源。
        fail_code: 如果传入特定的错误码（如频率限制），则触发冷却。
        """
        with self.cv:
            target_entity = None
            for entity in self.key_entities:
                if entity.api_key == api_key:
                    target_entity = entity
                    break
            
            if target_entity:
                with target_entity.lock:
                    target_entity.current_active -= 1
                    # 冷却逻辑：如果是频率限制（根据你的 API 报错码设定，假设是 429 或 -1）
                    if fail_code in [429, -1]:
                        target_entity.cooldown_until = time.time() + 60
                        print(f"⚠️ Key {target_entity.label} 进入60s冷却")
                
                # 重点：释放后广播通知，唤醒所有正在 acquire_key 中 wait 的任务
                self.cv.notify_all()


# 保持原有的 DataIO 逻辑
class DataIO:
    @staticmethod
    def load_json(file, default=None):
        if default is None: default = {}
        if os.path.exists(file):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: return default
        return default

    @staticmethod
    def save_json(file, data):
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)