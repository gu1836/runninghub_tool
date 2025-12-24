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
    "时空凝结": "frozen time effect, raindrops/splinters suspended in air",
    "梦境弥散": "dreamlike diffusion, soft focus shifts, floating dust or petals"
}# --- core_logic.py ---

MOTION_LIBRARY = [
    {
        "name": "凝视推进",
        "mode": "推镜头 (靠近)",
        "prompt": "slow, emotional push-in, focus intensifies on the subject's expression",
        "tags": ["靠近", "情感", "特写", "缓慢", "焦点", "放大", "聚焦", "内心"],
        "example": "场景：角色独白、情绪转折、发现线索。\n效果：视线向角色核心缓缓靠拢，增强紧张感或亲密感。"
    },
    {
        "name": "探索摇移",
        "mode": "横摇/平移",
        "prompt": "smooth cinematic pan, revealing the extended scene",
        "tags": ["平移", "全景", "寻找", "环境", "展开", "左右", "风景", "过场"],
        "example": "场景：展示广阔环境、跟随角色走动、揭示隐藏物体。\n效果：模拟人眼观察环境，视野平稳横向展开。"
    },
    {
        "name": "悬停环绕",
        "mode": "环绕镜头 (3/4环绕)",
        "prompt": "slow orbiting shot around the central subject, 3/4 view, cinematic lighting",
        "tags": ["转圈", "立体", "全方位", "高光", "英雄时刻", "环绕"],
        "example": "场景：展示角色全身设计、战斗前的对峙、重要物品展示。\n效果：镜头围绕主体旋转，增强空间感和史诗感。"
    },
    {
        "name": "呼吸感浮动",
        "mode": "手持感 (微动)",
        "prompt": "subtle handheld breathing effect, very slow and natural camera drift",
        "tags": ["真实", "日常", "手持", "呼吸", "生活化", "自然", "漂浮"],
        "example": "场景：日常对话、宁静的室内、等待的时刻。\n效果：模拟摄影师手持拍摄的细微晃动，增加画面的真实生活感。"
    },
    {
        "name": "升降揭示",
        "mode": "摇臂升降",
        "prompt": "smooth crane movement, perspective shifts vertically from low to high",
        "tags": ["上升", "俯瞰", "揭开", "壮观", "垂直", "宏大", "高度"],
        "example": "场景：从地面升起到远望城市、展示建筑物高度。\n效果：视角垂直高度发生变化，通常用于影片的开场或结尾。"
    },
    {
        "name": "关键帧顿挫",
        "mode": "动画节奏",
        "prompt": "animatic rhythm, slight holds on key poses, hand-drawn feel",
        "tags": ["卡顿", "张力", "二次元", "节奏", "动作", "有力", "动漫", "力量"],
        "example": "场景：高难度动作pose、打击感展示。\n效果：模拟动画“一拍二”节奏，在视觉重心处略有停顿，增强爆发力。"
    },
    {
        "name": "残影爆发",
        "mode": "视觉特效 (Smear)",
        "prompt": "smear frames action start, dynamic motion blur with afterimages",
        "tags": ["速度", "瞬移", "挥刀", "出拳", "快", "爆发", "幻影", "攻击"],
        "example": "场景：角色突然加速、挥剑瞬间、超能力发动。\n效果：主体启动时拖出多个半透明残影，视觉冲击力极强。"
    },
    {
        "name": "震屏冲击",
        "mode": "屏幕震动",
        "prompt": "impact frame with strong screen shake, followed by quick stabilization",
        "tags": ["爆炸", "打击", "怒吼", "震撼", "力量", "碰撞", "落地", "震动"],
        "example": "场景：重物落地、剧烈碰撞、角色愤怒爆发。\n效果：通过短促的屏幕抖动模拟物理撞击产生的空气震荡。"
    },
    {
        "name": "缩放冲击",
        "mode": "快速拉近 (Zoom)",
        "prompt": "anime-style quick zoom, with a slight screen jerk for emphasis",
        "tags": ["惊讶", "发现", "锁定", "突然", "瞪眼", "注目", "拉近", "特写"],
        "example": "场景：角色惊恐瞬间、发现关键证据、强调某个细节。\n效果：极速放大到某个局部，产生强烈的视觉引导和震撼感。"
    },
    {
        "name": "背景流线",
        "mode": "背景模糊 (速度感)",
        "prompt": "speed lines background effect, environment blurs into motion lines",
        "tags": ["飞行", "奔跑", "冲刺", "速度线", "快", "运动", "竞速", "赶路"],
        "example": "场景：角色高速奔跑、飞行、驾驶载具。\n效果：主体保持清晰，背景化为抽象的速度线条，体现极致速度。"
    },
    {
        "name": "风动万物",
        "mode": "环境联动",
        "prompt": "unified wind effect, hair, clothing, and foliage swaying in sync",
        "tags": ["飘动", "柔和", "自然", "室外", "头发", "衣服", "微风", "灵动"],
        "example": "场景：站在山头远眺、微风拂过的街道、披风展示。\n效果：让画面中所有软体（毛发、布料）沿统一方向节奏性摆动。"
    },
    {
        "name": "能量脉动",
        "mode": "光影动态",
        "prompt": "pulsing glow effect, with light particles emanating rhythmically",
        "tags": ["发光", "魔法", "核心", "呼吸灯", "节奏", "能量", "科幻", "粒子"],
        "example": "场景：魔法阵激活、机甲核心启动、角色觉醒。\n效果：光效伴随节奏忽明忽暗，像心脏跳动一样具有生命感。"
    },
    {
        "name": "时空凝结",
        "mode": "慢动作 (冻结)",
        "prompt": "frozen time effect, raindrops or splinters suspended in air, high speed camera",
        "tags": ["子弹时间", "慢速", "精致", "停滞", "细节", "雨点", "碎片"],
        "example": "场景：玻璃破碎、雨中漫步、爆炸瞬间。\n效果：周围物体几乎静止，唯有极其细微的动作，展示瞬间的极致细节。"
    },
    {
        "name": "梦境弥散",
        "mode": "氛围动态 (柔焦)",
        "prompt": "dreamlike diffusion, soft focus shifts, floating dust or petals",
        "tags": ["唯美", "回忆", "幻想", "发光", "浪漫", "粒子", "柔和", "散景"],
        "example": "场景：角色思念、梦境世界、浪漫的邂逅。\n效果：画面充满弥散的光斑和漂浮物，焦点虚实结合，梦幻感十足。"
    },
    {
        "name": "俯冲贴地",
        "mode": "低空掠过",
        "prompt": "rapid low-altitude drone shot, camera skimming the ground surface",
        "tags": ["低空", "飞行", "惊险", "视角", "极速", "贴地", "俯冲"],
        "example": "场景：飞越草地、紧贴水面飞行、地毯式搜索视角。\n效果：模拟无人机紧贴地面快速掠过，带给观众极强的代入感。"
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