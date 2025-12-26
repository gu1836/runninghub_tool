import tkinter as tk
from tkinter import ttk, messagebox
import core_logic

class DirectorEditor(tk.Toplevel):
    def __init__(self, master, max_duration, global_camera, has_dialogue, initial_data=None, callback=None):
        """
        :param max_duration: 任务总时长 (10 或 15)
        :param global_camera: 主界面当前的全局相机 short_prompt
        :param has_dialogue: 布尔值，台词框是否有内容
        :param initial_data: 用于恢复数据的列表 (可选)
        :param callback: 保存时的回调函数，传回 (data_list, is_custom_camera)
        """
        super().__init__(master)
        self.max_duration = float(max_duration)
        self.global_camera = global_camera
        self.has_dialogue = has_dialogue
        self.callback = callback
        
        self.title(f"导演分镜编辑器 - 目标总时长: {self.max_duration}s")
        self.geometry("950x550")
        self.grab_set()  # 模态窗口，防止操作主界面
        
        # 数据存储
        self.shot_rows = []
        self.sync_var = tk.IntVar(value=-1)  # 用于台词同步的单选逻辑
        
        # 注册验证逻辑：只能输入 0 到 max_duration 之间的数字
        self.vcmd = (self.register(self._validate_time), '%P')
        
        self._setup_ui()
        
        # 加载逻辑
        if initial_data and len(initial_data) > 0:
            self._load_initial_data(initial_data)
        else:
            self.add_row(start_time=0.0)

    def _setup_ui(self):
        """初始化UI布局"""
        # 顶部操作栏
        top_bar = ttk.Frame(self)
        top_bar.pack(fill="x", padx=15, pady=10)
        
        ttk.Label(top_bar, text=f"📊 时间轴配置 ({self.max_duration}s)", font=("Arial", 10, "bold")).pack(side="left")
        
        self.btn_add_row = ttk.Button(top_bar, text="➕ 添加分镜切片", command=self.add_row)
        self.btn_add_row.pack(side="right")

        # 表头
        header = ttk.Frame(self)
        header.pack(fill="x", padx=15)
        cols = [("开始 (s)", 8), ("结束 (s)", 8), ("核心动作 (Subject Action)", 25), 
                ("相机运镜 (Camera)", 20), ("视觉细节 (Environment)", 30), ("说话", 5)]
        for text, width in cols:
            ttk.Label(header, text=text, width=width, anchor="w").pack(side="left", padx=2)

        # 滚动区域实现
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, padx=15, pady=5)
        
        self.canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.scroll_frame = ttk.Frame(self.canvas)

        self.scroll_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 底部操作栏
        footer = ttk.Frame(self)
        footer.pack(fill="x", padx=15, pady=15)
        
        ttk.Label(footer, text="提示：若自定义运镜，将覆盖全局相机设置；Sync 仅在有台词时可用。", 
                  foreground="gray").pack(side="left")
        
        ttk.Button(footer, text="取消", command=self.destroy).pack(side="right", padx=5)
        ttk.Button(footer, text="✅ 确认并同步脚本", command=self.save_data).pack(side="right", padx=5)

    def _validate_time(self, new_value):
        """实时校验输入范围"""
        if new_value == "" or new_value == ".": return True
        try:
            val = float(new_value)
            return 0 <= val <= self.max_duration
        except ValueError:
            return False

    def check_button_state(self, event=None):
        """状态检查：如果最后一行已达总时长，禁用添加按钮"""
        if not self.shot_rows: return
        try:
            last_end = float(self.shot_rows[-1]['end'].get() or 0)
            if last_end >= self.max_duration:
                self.btn_add_row.configure(state="disabled")
            else:
                self.btn_add_row.configure(state="normal")
        except ValueError:
            self.btn_add_row.configure(state="normal")

    def add_row(self, start_time=None, data=None):
        """添加新行"""
        if start_time is None:
            try:
                start_time = float(self.shot_rows[-1]['end'].get() or 0)
            except:
                start_time = 0.0

        row_idx = len(self.shot_rows)
        row_frame = ttk.Frame(self.scroll_frame)
        row_frame.pack(fill="x", pady=3)

        # 1. 时间区间 (保持不变)
        ent_s = ttk.Entry(row_frame, width=8, validate='key', validatecommand=self.vcmd)
        ent_s.insert(0, str(start_time))
        ent_s.pack(side="left", padx=2)

        ent_e = ttk.Entry(row_frame, width=8, validate='key', validatecommand=self.vcmd)
        ent_e.pack(side="left", padx=2)
        ent_e.bind("<KeyRelease>", self.check_button_state)

        # 2. 核心动作
        ent_act = ttk.Entry(row_frame, width=25)
        ent_act.pack(side="left", padx=2)

        # --- 【关键修改】：将 Entry 改为 Combobox ---
        # 准备下拉列表：从 core_logic 获取所有镜头名称
        motion_names = [item["name"] for item in core_logic.MOTION_LIBRARY]
        
        # 创建下拉框
        cb_cam = ttk.Combobox(row_frame, values=motion_names, width=18, state="readonly")
        
        # 初始值逻辑：
        # 如果 global_camera 传入的是 short_prompt，我们需要反向查找它的 name 显示在 UI 上
        initial_display_name = ""
        for item in core_logic.MOTION_LIBRARY:
            if item["short_prompt"] == self.global_camera:
                initial_display_name = item["name"]
                break
        
        cb_cam.set(initial_display_name if initial_display_name else motion_names[0])
        cb_cam.pack(side="left", padx=2)

        # 3. 视觉细节
        ent_vis = ttk.Entry(row_frame, width=30)
        ent_vis.pack(side="left", padx=2)

        # 4. 台词同步与删除按钮 (保持不变)
        state = "normal" if self.has_dialogue else "disabled"
        rb = ttk.Radiobutton(row_frame, variable=self.sync_var, value=row_idx, state=state)
        rb.pack(side="left", padx=10)

        del_btn = ttk.Button(row_frame, text="✕", width=3, 
                             command=lambda: self.remove_row(row_frame, row_info))
        del_btn.pack(side="left", padx=2)

        row_info = {
            "frame": row_frame, "start": ent_s, "end": ent_e,
            "action": ent_act, "camera": cb_cam, "visual": ent_vis
        }
        
        # 加载旧数据时的特殊处理
        if data:
            ent_e.insert(0, data.get("end", ""))
            ent_act.insert(0, data.get("action", ""))
            ent_vis.insert(0, data.get("visual", ""))
            # 如果存档里存的是 short_prompt，转换回 name 显示
            saved_cam_short = data.get("camera", "")
            for item in core_logic.MOTION_LIBRARY:
                if item["short_prompt"] == saved_cam_short:
                    cb_cam.set(item["name"])
                    break
            if data.get("sync_speech"): self.sync_var.set(row_idx)

        self.shot_rows.append(row_info)
        self.check_button_state()

    def save_data(self):
        """保存时：将 Combobox 的 name 转换回 short_prompt"""
        self.focus_set()
        if not self.shot_rows: return
        
        # ... (时间检查逻辑保持不变) ...

        compiled_data = []
        is_custom_camera = False
        
        for i, row in enumerate(self.shot_rows):
            # 获取下拉框选中的中文名称
            selected_name = row["camera"].get()
            
            # 【核心转换】：从名称转回 short_prompt
            current_short_prompt = ""
            for item in core_logic.MOTION_LIBRARY:
                if item["name"] == selected_name:
                    current_short_prompt = item["short_prompt"]
                    break
            
            # 判断是否修改了全局相机
            if current_short_prompt != self.global_camera:
                is_custom_camera = True
            
            compiled_data.append({
                "start": row["start"].get(),
                "end": row["end"].get(),
                "action": row["action"].get(),
                "camera": current_short_prompt, # 存储的是英文指令
                "visual": row["visual"].get(),
                "sync_speech": (self.sync_var.get() == i)
            })

        if self.callback:
            self.callback(compiled_data, is_custom_camera)
        self.destroy()

    def remove_row(self, frame, data):
        if len(self.shot_rows) <= 1: return
        frame.destroy()
        self.shot_rows.remove(data)
        self.check_button_state()

    def _load_initial_data(self, data_list):
        """从外部列表恢复数据"""
        for item in data_list:
            self.add_row(start_time=item.get("start", 0.0), data=item)


    
    def get_short_camera_name(self, name):
        """根据中文名获取对应的英文短提示词 (用于 Table)"""
        if name == "无":
            return ""
        
        # 1. 先从内置库找
        for item in core_logic.MOTION_LIBRARY:
            if item["name"] == name:
                return item["short_prompt"]
        
        # 2. 再从自定义库找 (假设自定义库存的是字符串或字典)
        custom_data = self.app.custom_motions.get(name, "")
        if isinstance(custom_data, dict):
            return custom_data.get("short_prompt", name)
        return custom_data # 如果是纯字符串直接返回

    def get_full_camera_prompt(self, name):
        """根据中文名获取对应的详细提示词 (用于全局 Prompt)"""
        if name == "无":
            return ""
            
        for item in core_logic.MOTION_LIBRARY:
            if item["name"] == name:
                return item["prompt"]
        
        # 自定义库逻辑同上
        return self.app.custom_motions.get(name, "")