import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import threading
import time
import os
import re
import uuid
from datetime import datetime
import core_logic
from DirectorEditor import DirectorEditor

import runninghub

# --- 1. API Key 池管理窗口 ---
class KeyPoolEditor:
    def __init__(self, parent, app):
        self.app = app
        self.win = tk.Toplevel(parent)
        self.win.title("🔑 API Key 调度池管理")
        self.win.geometry("750x450")
        self.win.grab_set()

        # --- 1. 列表显示区 ---
        columns = ("label", "key", "limit")
        self.tree = ttk.Treeview(self.win, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("label", text="账号备注")
        self.tree.heading("key", text="API Key")
        self.tree.heading("limit", text="并发上限")
        self.tree.column("label", width=120)
        self.tree.column("key", width=350)
        self.tree.column("limit", width=80, anchor="center")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 绑定右键菜单
        self.tree.bind("<Button-3>", self.show_context_menu)

        # --- 2. 新增/编辑输入区 ---
        input_f = ttk.LabelFrame(self.win, text=" 账号配置 ", padding=10)
        input_f.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(input_f, text="备注:").pack(side=tk.LEFT)
        self.e_l = ttk.Entry(input_f, width=12)
        self.e_l.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(input_f, text="Key:").pack(side=tk.LEFT)
        self.e_k = ttk.Entry(input_f, width=30)
        self.e_k.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(input_f, text="上限:").pack(side=tk.LEFT)
        self.e_m = ttk.Entry(input_f, width=5)
        self.e_m.insert(0, "3") # 默认并发给3
        self.e_m.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(input_f, text="📝 更新/添加", command=self.add_item).pack(side=tk.LEFT, padx=10)

        # --- 3. 底部控制区 ---
        btn_f = ttk.Frame(self.win, padding=10)
        btn_f.pack(fill=tk.X)
        ttk.Button(btn_f, text="🗑️ 删除选中", command=self.del_item).pack(side=tk.LEFT)
        ttk.Button(btn_f, text="💾 保存应用", command=self.save_data).pack(side=tk.RIGHT)

        # --- 4. 右键菜单定义 ---
        self.menu = tk.Menu(self.win, tearoff=0)
        self.menu.add_command(label="📝 编辑此项", command=self.load_to_edit)
        self.menu.add_command(label="🔝 移至顶部", command=self.move_to_top)
        self.menu.add_separator()
        self.menu.add_command(label="🗑️ 删除此项", command=self.del_item)

        # 初始加载数据
        for item in self.app.api_pool:
            self.tree.insert("", tk.END, values=(item['label'], item['key'], item['limit']))

    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.menu.post(event.x_root, event.y_root)

    def load_to_edit(self):
        sel = self.tree.selection()
        if not sel: return
        vals = self.tree.item(sel[0], "values")
        self.e_l.delete(0, tk.END); self.e_l.insert(0, vals[0])
        self.e_k.delete(0, tk.END); self.e_k.insert(0, vals[1])
        self.e_m.delete(0, tk.END); self.e_m.insert(0, vals[2])

    def move_to_top(self):
        sel = self.tree.selection()
        if not sel: return
        self.tree.move(sel[0], "", 0)

    def add_item(self):
        l, k, m = self.e_l.get().strip(), self.e_k.get().strip(), self.e_m.get().strip()
        if not l or not k or not m: return
        
        # 检查是否是更新已有的 Key
        for child in self.tree.get_children():
            if self.tree.item(child, "values")[1] == k:
                self.tree.item(child, values=(l, k, m))
                return
        
        self.tree.insert("", tk.END, values=(l, k, m))

    def del_item(self):
        sel = self.tree.selection()
        for s in sel: self.tree.delete(s)

    def save_data(self):
        """核心：将 UI 数据同步到内存池，并触发布局通知"""
        new_pool = []
        for child in self.tree.get_children():
            v = self.tree.item(child, "values")
            new_pool.append({
                'label': v[0],
                'key': v[1],
                'limit': int(v[2])
            })
        
        # 1. 更新 App 原始配置数据
        self.app.api_pool = new_pool
        
        # 2. 【关键】通知 ResourceManager 重新构建 Key 实体并唤醒等待线程
        if hasattr(self.app, 'res_manager'):
            self.app.res_manager.update_pool(new_pool)
        
        # 3. 自动保存到本地 JSON 文件
        self.app.auto_save_all()
        
        # 4. 反馈
        from tkinter import messagebox
        messagebox.showinfo("成功", "API Key 池已更新并立即生效！")
        self.win.destroy()


# --- 2. 声纹管理窗口 ---
class VoiceTableEditor:
    def __init__(self, parent, app):
        self.app = app
        self.win = tk.Toplevel(parent)
        self.win.title("👥 声纹参数管理")
        self.win.geometry("600x500")
        self.win.grab_set()

        # --- 列表部分 ---
        columns = ("name", "params")
        self.tree = ttk.Treeview(self.win, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("name", text="角色名")
        self.tree.heading("params", text="声纹参数")
        self.tree.column("name", width=150)
        self.tree.column("params", width=400)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 绑定右键菜单
        self.tree.bind("<Button-3>", self.show_context_menu)

        # --- 操作输入区 ---
        f_input = ttk.LabelFrame(self.win, text="编辑/新增", padding=10)
        f_input.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(f_input, text="角色:").pack(side=tk.LEFT)
        self.en = ttk.Entry(f_input, width=12)
        self.en.pack(side=tk.LEFT, padx=2)
        
        ttk.Label(f_input, text="参数:").pack(side=tk.LEFT)
        self.ep = ttk.Entry(f_input, width=30)
        self.ep.pack(side=tk.LEFT, padx=2)
        
        ttk.Button(f_input, text="➕ 添加/更新", command=self.add_or_update).pack(side=tk.LEFT, padx=5)

        # --- 控制按钮区 ---
        f_btns = ttk.Frame(self.win, padding=10)
        f_btns.pack(fill=tk.X)
        
        #ttk.Button(f_btns, text="❌ 删除选中项", command=self.delete_item).pack(side=tk.LEFT, padx=10)
        ttk.Button(f_btns, text="💾 保存并同步所有任务", command=self.save).pack(side=tk.RIGHT, padx=10)

        # --- 右键菜单定义 ---
        self.menu = tk.Menu(self.win, tearoff=0)
        self.menu.add_command(label="📝 修改此项", command=self.load_to_entry)
        self.menu.add_separator()
        self.menu.add_command(label="🗑️ 删除此项", command=self.delete_item)

        # 初始化数据加载
        for n, p in self.app.voice_lib.items():
            self.tree.insert("", tk.END, values=(n, p))

    def show_context_menu(self, event):
        """显示右键菜单并自动选中该行"""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.menu.post(event.x_root, event.y_root)

    def load_to_entry(self):
        """将选中的数据加载到下方的输入框中进行修改"""
        selected = self.tree.selection()
        if not selected: return
        vals = self.tree.item(selected[0])['values']
        self.en.delete(0, tk.END); self.en.insert(0, vals[0])
        self.ep.delete(0, tk.END); self.ep.insert(0, vals[1])

    def add_or_update(self):
        """如果角色名已存在则更新，否则新增"""
        name = self.en.get().strip()
        params = self.ep.get().strip()
        if not name: return

        # 检查是否已存在同名行
        for item in self.tree.get_children():
            if self.tree.item(item)['values'][0] == name:
                self.tree.item(item, values=(name, params))
                return
        
        # 不存在则新增
        self.tree.insert("", tk.END, values=(name, params))
        self.en.delete(0, tk.END); self.ep.delete(0, tk.END)

    def delete_item(self):
        """删除当前选中项"""
        selected = self.tree.selection()
        for item in selected:
            self.tree.delete(item)



    def save(self):
        new_lib = {}
        for i in self.tree.get_children():
            v = self.tree.item(i)['values']
            # 关键修改：将值存为一个字典，而不仅仅是字符串
            new_lib[str(v[0])] = {
                "desc": str(v[1]),  # 这里的 v[1] 是你在参数框填的 Prompt
                "v_id": ""         # 预留给声纹ID
            }
        
        self.app.voice_lib = new_lib
        self.app.auto_save_all()
        
        # 通知所有任务卡片刷新下拉列表
        for t in self.app.tasks: 
            t.update_voice_list()
            
        self.win.destroy()


# --- 3. 任务卡片 ---
class TaskCard:
    def __init__(self, parent, app, data=None):

        self.app = app
        self.data = data if isinstance(data, dict) else {}
        self.task_id = self.data.get("task_id", str(uuid.uuid4()))

        # --- 【新增】DirectorEditor 分镜数据存储 ---
        
        # 恢复存档中的分镜数据，如果没有则设为空列表
        self.saved_shot_data = self.data.get("shot_notes_data", []) 
        # 恢复是否为自定义运镜的状态
        self.is_custom_camera = self.data.get("is_custom_camera", False)

        # --- 【原有】方案 B 状态变量 ---
        self.pending_timer = None
        # 记录上一次稳定在栈里的内容快照
        self.last_stable_prompt = self.data.get("prompt", "")
        self.last_stable_script = self.data.get("script", "")
        
        # 将自己注册到主程序的映射表中
        self.app.task_mapping[self.task_id] = self
        self.frame = ttk.LabelFrame(parent, text=" 镜头卡片 ", padding=10)
        self.frame.pack(fill=tk.X, padx=15, pady=8)
        self.file_path = self.data.get("img_path", "")
        self.is_running = False
        
        self.setup_ui()
        
        if self.file_path: 
            self.load_thumbnail(self.file_path)
        
        # 如果已有分镜数据，初始化时更新一下按钮样式
        self._update_editor_btn_style()

    def setup_ui(self):
        # --- 1. 映射关系定义 ---
        self.ratio_map = {
            "竖屏 (9:16)": "portrait",
            "横屏 (16:9)": "landscape",
            "竖屏高清": "portrait-hd",
            "横屏高清": "landscape-hd"
        }
        self.ratio_rev_map = {v: k for k, v in self.ratio_map.items()}
        self.dur_map = {"10秒": "10s", "15秒": "15s"}
        self.dur_rev_map = {v: k for k, v in self.dur_map.items()}

        # --- 2. 界面布局 ---
        # 左侧：预览
        self.l_col = tk.Frame(self.frame, width=120, height=120, bg="#e9ecef")
        self.l_col.pack(side=tk.LEFT, padx=5)
        self.l_col.pack_propagate(False)
        self.lbl_t = tk.Label(self.l_col, text="无图", bg="#e9ecef")
        self.lbl_t.pack(expand=True, fill=tk.BOTH)
        
        # 按钮区
        b_box = tk.Frame(self.frame)
        b_box.pack(side=tk.LEFT)
        ttk.Button(b_box, text="选图", width=6, command=self.select_file).pack(pady=2)
        ttk.Button(b_box, text="删除", width=6, command=self.delete_card).pack(pady=2)

        # 中间：编辑区
        mid = tk.Frame(self.frame)
        mid.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        
        # --- 提示词输入区 ---
        ttk.Label(mid, text="提示词输入:", font=("微软雅黑", 9, "bold")).pack(anchor=tk.W)
        # 【修改】undo=False
        self.txt_p = tk.Text(mid, height=3, font=("微软雅黑", 9), undo=False)
        self.txt_p.pack(fill=tk.X, pady=(0, 5))
        self.txt_p.insert("1.0", self.last_stable_prompt)
        self.txt_p.parent_card = self  # 【新增】反向引用

        # --- 台词内容区 ---
        ttk.Label(mid, text="台词内容:", font=("微软雅黑", 9, "bold")).pack(anchor=tk.W)
        # 【修改】undo=False
        self.txt_s = tk.Text(mid, height=1, font=("微软雅黑", 9, "bold"), undo=False)
        self.txt_s.pack(fill=tk.X, pady=(0, 5))
        self.txt_s.insert("1.0", self.last_stable_script)
        self.txt_s.parent_card = self  # 【新增】反向引用

        # --- 【关键绑定】 ---
        # 监听实质性内容变化（支持中文上屏、粘贴、删除）
        self.txt_p.bind("<<Modified>>", self._on_text_modified)
        self.txt_s.bind("<<Modified>>", self._on_text_modified)

        # 失去焦点时立即结算（防止未满1秒就切换卡片导致记录丢失）
        self.txt_p.bind("<FocusOut>", lambda e: self.force_settle())
        self.txt_s.bind("<FocusOut>", lambda e: self.force_settle())

        # --- 控制行 ---
        ctrl = tk.Frame(mid) 
        ctrl.pack(fill=tk.X)
        
        # 1. 动态指令选择
        #ttk.Label(ctrl, text="动态:").pack(side=tk.LEFT)
        #self.cb_motion = ttk.Combobox(ctrl, state="readonly", width=10)
        #self.cb_motion.pack(side=tk.LEFT, padx=2)
        
        # 【新增】搜索匹配按钮：点击打开可视化搜索手册
        #self.btn_motion_search = ttk.Button(
        #    ctrl, 
        #    text="🔍", 
        #    width=3, 
            # 错误写法：lambda: MotionSearcher(self.app.root, self.set_motion_by_name)
            # 正确写法：必须传入 self.app 实例
        #    command=lambda: MotionSearcher(self.app.root, self.app, self.set_motion_by_name)
        #)
        #self.btn_motion_search.pack(side=tk.LEFT, padx=(0, 5))

        #self.update_motion_list() # 初始化列表加载存档
        #self.cb_motion.bind("<<ComboboxSelected>>", lambda e: self.app.auto_save_all())
        
        # 2. 角色选择
        #ttk.Label(ctrl, text="角色:").pack(side=tk.LEFT)
        #self.cb = ttk.Combobox(ctrl, state="readonly", width=8)
        #self.update_voice_list()
        #self.cb.pack(side=tk.LEFT, padx=2)
        #if self.data.get("char"): self.cb.set(self.data["char"])
        #self.cb.bind("<<ComboboxSelected>>", lambda e: self.app.auto_save_all())
        # 1. 动态指令选择
        ttk.Label(ctrl, text="动态:").pack(side=tk.LEFT)
        self.cb_motion = ttk.Combobox(ctrl, state="readonly", width=10)
        self.cb_motion.pack(side=tk.LEFT, padx=2)
        self.update_motion_list() 

        # 【新增】导演脚本编辑按钮
        self.btn_director = ttk.Button(
            ctrl, 
            text="🎬 导演", 
            width=5, 
            command=self.open_director_editor
        )
        self.btn_director.pack(side=tk.LEFT, padx=2)

        # 2. 角色选择
        ttk.Label(ctrl, text="角色:").pack(side=tk.LEFT)
        self.cb = ttk.Combobox(ctrl, state="readonly", width=8)
        self.update_voice_list()
        self.cb.pack(side=tk.LEFT, padx=2)
        saved_char = self.data.get("char")
        if saved_char: self.cb.set(saved_char)

        # 3. 比例选择
        ttk.Label(ctrl, text="比例:").pack(side=tk.LEFT)
        self.cb_ratio = ttk.Combobox(ctrl, values=list(self.ratio_map.keys()), width=12, state="readonly")
        ratio_text_preset = self.data.get("ratio_text")
        if ratio_text_preset:
            self.cb_ratio.set(ratio_text_preset)
        else:
            saved_ratio_key = self.data.get("ratio", "landscape")
            self.cb_ratio.set(self.ratio_rev_map.get(saved_ratio_key, "横屏 (16:9)"))
        self.cb_ratio.pack(side=tk.LEFT, padx=2)

        # 4. 时长选择
        ttk.Label(ctrl, text="时长:").pack(side=tk.LEFT)
        self.cb_dur = ttk.Combobox(ctrl, values=list(self.dur_map.keys()), width=6, state="readonly")
        dur_text_preset = self.data.get("duration_text")
        if dur_text_preset:
            self.cb_dur.set(dur_text_preset)
        else:
            saved_dur_key = self.data.get("duration", "10s")
            self.cb_dur.set(self.dur_rev_map.get(saved_dur_key, "10秒"))
        self.cb_dur.pack(side=tk.LEFT, padx=2)
        
        # 事件绑定
        self.cb.bind("<<ComboboxSelected>>", self._on_ui_change)
        self.cb_motion.bind("<<ComboboxSelected>>", self._on_ui_change)
        self.cb_ratio.bind("<<ComboboxSelected>>", self._on_ui_change)
        self.cb_dur.bind("<<ComboboxSelected>>", self._on_ui_change)


        # 5. 运行按钮与状态显示
        self.btn = ttk.Button(ctrl, text="▶ 运行", command=self.start)
        self.btn.pack(side=tk.LEFT, padx=5)
        
        self.lbl_st = ttk.Label(ctrl, text="就绪", foreground="gray")
        self.lbl_st.pack(side=tk.LEFT)
        
        self.lbl_tm = ttk.Label(ctrl, text="00:00")
        self.lbl_tm.pack(side=tk.RIGHT)


    def open_director_editor(self):
        """打开分镜编辑器"""
        from DirectorEditor import DirectorEditor # 确保已导入
        
        # 获取当前任务时长（数字）
        dur_text = self.cb_dur.get()
        max_dur = 15 if "15" in dur_text else 10
        
        # 获取当前全局相机的短描述
        motion_name = self.cb_motion.get()
        # 这里需要你有一个能从名字查到 short_prompt 的方法，或者直接传名字
        global_cam_short = motion_name 
        
        # 检查台词框内容
        has_dialogue = len(self.txt_s.get("1.0", "end-1c").strip()) > 0
        
        # 打开窗口
        DirectorEditor(
            master=self.app.root, 
            max_duration=max_dur,
            global_camera=global_cam_short,
            has_dialogue=has_dialogue,
            # 【关键】如果这里不传，编辑器每次打开都是空白的
            initial_data=self.saved_shot_data, 
            callback=self.on_director_save
        )

    def on_director_save(self, new_data, new_custom):
        """当编辑器点击确认时"""
        # 1. 检查数据是否有实质变化，避免无效撤销步骤
        if new_data == self.saved_shot_data and new_custom == self.is_custom_camera:
            return

        # 2. 记录动作到全局 Undo 栈
        self.app.action_manager.push_action("EDIT_SHOTS", {
            "task_id": self.task_id,
            "old_data": self.saved_shot_data,  # 之前的快照
            "new_data": new_data,             # 现在的快照
            "old_custom": self.is_custom_camera,
            "new_custom": new_custom
        })

        # 3. 更新当前内存数据
        self.saved_shot_data = new_data
        self.is_custom_camera = new_custom
        
        # 4. 更新 UI 和保存
        self._update_editor_btn_style()
        if hasattr(self.app, 'auto_save_all'):
            self.app.auto_save_all()

    def _update_editor_btn_style(self):
        """根据是否有数据更新按钮外观"""
        if self.saved_shot_data:
            # 如果有数据，按钮文字加粗或变色
            self.btn_director.configure(text="🎬 [编]") 
        else:
            self.btn_director.configure(text="🎬 导演")


    def _on_ui_change(self, event=None):
        """当 Combobox 等组件改变时触发的统一保存逻辑"""
        # 如果有预览需求，在这里调用
        if event and event.widget == self.cb_motion:
            self.update_motion_preview(self.cb_motion.get())
        
        # 触发全局物理存盘
        self.app.auto_save_all()

    def _on_text_modified(self, event):
        """当文字改变时触发（由虚拟信号驱动）"""
        widget = event.widget
        # 只有当确实发生了实质性修改时才处理
        if widget.edit_modified():
            if self.pending_timer:
                self.app.root.after_cancel(self.pending_timer)
            
            # 1000ms 停顿后执行记录
            self.pending_timer = self.app.root.after(1000, self.force_settle)
            
            # 重置标志位以接收下一次信号
            widget.edit_modified(False)

    def force_settle(self):
        """立即结算当前的编辑动作"""
        if self.pending_timer:
            self.app.root.after_cancel(self.pending_timer)
            self.pending_timer = None
        
        # 检查两个文本框是否需要推入栈
        self._check_and_push("txt_p", self.last_stable_prompt)
        self._check_and_push("txt_s", self.last_stable_script)

    def _check_and_push(self, attr_name, old_val):
        """对比并入栈的内部逻辑"""
        widget = getattr(self, attr_name)
        current_text = widget.get("1.0", "end-1c")
        
        if current_text != old_val:
            field_alias = "prompt" if attr_name == "txt_p" else "script"
            
            # 记录到全局经理
            self.app.action_manager.push_action("EDIT_TEXT", {
                "task_id": self.task_id,
                "field": attr_name,
                "old_val": old_val,
                "new_val": current_text
            })
            
            # 更新该字段对应的稳定快照
            if attr_name == "txt_p": self.last_stable_prompt = current_text
            else: self.last_stable_script = current_text
            
            # 触发物理存档
            self.app.auto_save_all()

    def set_text_silent(self, attr_name, text):
        """撤销重做系统专用的静默设置方法"""
        widget = getattr(self, attr_name)
        
        # 解绑监听，防止撤销本身产生新的记录导致死循环
        widget.unbind("<<Modified>>")
        
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        
        # 强制同步快照
        if attr_name == "txt_p": self.last_stable_prompt = text
        else: self.last_stable_script = text
        
        # 重置标志位并重新绑定
        widget.edit_modified(False)
        widget.bind("<<Modified>>", self._on_text_modified)
        
        # 如果该卡片在视野外，滚动使其可见（可选增强体验）
        widget.see("insert")
    
    def set_motion_by_name(self, name):
        """供 MotionSearcher 调用的回调，实现静默设置"""
        self.cb_motion.set(name)
        self.app.auto_save_all()


    def get_short_camera_name(self, name):
        """根据中文名获取对应的英文短提示词 (用于 DirectorEditor Table)"""
        if name == "无": return ""
        
        # 1. 检索内置库
        import core_logic
        for item in core_logic.MOTION_LIBRARY:
            if item["name"] == name:
                return item.get("short_prompt", "")
        
        # 2. 检索自定义库
        custom_motions = getattr(self.app, 'custom_motions', {})
        custom_data = custom_motions.get(name, "")
        return custom_data.get("short_prompt", name) if isinstance(custom_data, dict) else custom_data

    def get_full_camera_prompt(self, name):
        """根据中文名获取对应的详细提示词 (用于全局 Final Prompt)"""
        if name == "无": return ""
            
        import core_logic
        for item in core_logic.MOTION_LIBRARY:
            if item["name"] == name:
                return item.get("prompt", "")
        
        # 检索自定义库
        custom_motions = getattr(self.app, 'custom_motions', {})
        custom_data = custom_motions.get(name, "")
        return custom_data.get("prompt", custom_data) if isinstance(custom_data, dict) else custom_data
    

    def update_motion_list(self):
        """刷新动态下拉列表（从 MOTION_LIBRARY 列表结构加载）"""
        # 1. 从 core_logic 里的列表提取名称
        # 假设 MOTION_LIBRARY = [{"name": "特写镜头", ...}, ...]
        #import core_logic
        builtin_names = [item["name"] for item in core_logic.MOTION_LIBRARY]
        
        # 2. 提取自定义运动的名称 (兼容性处理)
        custom_motions = getattr(self.app, 'custom_motions', {})
        custom_names = list(custom_motions.keys())
        
        # 3. 合并列表并更新 UI
        all_keys = ["无"] + builtin_names + custom_names
        self.cb_motion['values'] = all_keys
        
        # 4. 恢复存档数据
        saved_key = self.data.get("motion_key", "无")
        self.cb_motion.set(saved_key if saved_key in all_keys else "无")
            
        # 5. 刷新预览
        if hasattr(self, 'update_motion_preview'):
            self.update_motion_preview(self.cb_motion.get())

    def on_motion_change(self, e):
        """当用户选择不同的动态效果时"""
        key = self.cb_motion.get()
        self.update_motion_preview(key)
        self.app.auto_save_all()

    def update_motion_preview(self, key):
        """在界面显示选中的指令预览"""
        full_lib = {**core_logic.DEFAULT_MOTIONS, **self.app.custom_motions}
        desc = full_lib.get(key, "")
        # 截断显示，防止UI撑开
        display_text = (desc[:35] + '...') if len(desc) > 35 else desc
        #self.lbl_motion_preview.config(text=display_text)

    def get_final_prompt(self):
        """
        核心逻辑：组合全局描述、分镜脚本、角色声纹、相机指令以及台词。
        已集成：AttributeError 异常防御、声纹描述注入、自定义运镜优先级判定。
        """
        # 1. 基础信息获取
        user_p = self.txt_p.get("1.0", "end-1c").strip()
        script_text = self.txt_s.get("1.0", "end-1c").strip()
        
        # 2. 角色声纹 Prompt 提取 (含安全性校验，防止旧数据导致报错)
        char_name = self.cb.get()
        char_info = self.app.voice_lib.get(char_name, {})
        
        char_prompt = ""
        if isinstance(char_info, dict):
            # 适配 VoiceTableEditor 存储的新字典格式
            char_prompt = char_info.get("desc", "").strip()
        elif isinstance(char_info, str):
            # 兼容旧版本的纯字符串格式
            char_prompt = char_info.strip()
            
        # 生成角色标识符，例如: (小明: 穿着校服的少年)
        char_tag = f"({char_name}: {char_prompt})" if char_prompt else f"({char_name})"

        # 3. 编译分镜脚本 (来自 DirectorEditor Table)
        shot_notes_str = ""
        has_synced_speech = False
        
        # 检查是否有保存过分镜数据
        saved_data = getattr(self, 'saved_shot_data', [])
        if saved_data:
            segments = []
            for item in saved_data:
                # 基础行：时间 + 动作
                line = f"{item['start']}–{item['end']}s: [{item['action']}]"
                
                # 如果开启了自定义运镜模式，在行内集成 Table 选中的 short_prompt
                if getattr(self, 'is_custom_camera', False):
                    line += f" with {item['camera']} movement"
                
                # 集成视觉细节描述
                if item.get('visual'):
                    line += f", {item['visual']}"
                
                # 集成角色台词同步 (注入角色声纹描述)
                if item.get('sync_speech') and script_text:
                    line += f" | Character {char_tag} speaking: \"{script_text}\""
                    has_synced_speech = True
                
                segments.append(line)
            shot_notes_str = ";\n".join(segments)

        # 4. 组合最终 Prompt 列表
        final_parts = []
        
        # A. 全局场景描述
        if user_p: 
            final_parts.append(f"[Global Scene]: {user_p}")
        
        # B. 详细导演分镜脚本
        if shot_notes_str: 
            final_parts.append(f"[Director's Shot Notes]:\n{shot_notes_str}")
        
        # C. 全局相机逻辑 (仅当没有在 Table 里自定义相机时生效)
        if not getattr(self, 'is_custom_camera', False):
            motion_name = self.cb_motion.get()
            # 通过你之前定义的 get_full_camera_prompt 获取详细描述
            motion_p = self.get_full_camera_prompt(motion_name)
            if motion_p:
                final_parts.append(f"[Global Camera]: {motion_p}")
            
        # D. 台词内容兜底 (如果在 Table 里没勾选 Sync，则放在最后作为全局台词)
        if script_text and not has_synced_speech:
            final_parts.append(f"[Dialogue Content] {char_tag}: \"{script_text}\"")

        # 5. 使用双换行连接各板块，增强 AI 阅读清晰度
        full_prompt = "\n\n".join(final_parts)
        
        return full_prompt
    # --- 以下为功能方法保持不变 ---

    def select_file(self):
        p = filedialog.askopenfilename(
            filetypes=[("图像文件", "*.png *.jpg *.jpeg *.webp")]
        )
        if p: 
            self.file_path = p
            self.load_thumbnail(p)
            # 确保路径变动后立即触发自动保存
            self.app.auto_save_all()

    # TaskCard 类内部
    def delete_card(self):
        if self.is_running:
            messagebox.showwarning("警告", "该任务正在运行中，无法删除！")
            return

    # 2. 用户确认
        if messagebox.askyesno("删除", "确定删除此卡片？"):
        # 3. 调用 App 层的精准销毁（这步会触发 ActionManager 记录动作）
            self.app.destroy_card_by_id(self.task_id, record=True)
       
    def _notify_change(self, event=None):
        """通用变更通知：任何 UI 变动都指向这里"""
        # 1. 只有在非撤销/重做期间才触发（可选，防止循环）
        # 2. 触发全局保存
        self.app.auto_save_all()
# TaskCard 内部建议的清理函数
# --- 修改 TaskCard 内部的 delete_card_clean ---
    def delete_card_clean(self):
        self.is_running = False 
        
        # 1. 从主程序的全局列表中移除
        if self in self.app.tasks:
            self.app.tasks.remove(self)
        
        # 2. 从主程序的映射字典中移除 (使用我们刚写的清理函数)
        self.app.remove_task_reference(self.task_id)
        
        # 3. 销毁 UI
        try:
            self.frame.destroy()
        except:
            pass

    def load_thumbnail(self, p):
        try:
            img = Image.open(p); img.thumbnail((120, 120))
            self.tk_img = ImageTk.PhotoImage(img)
            self.lbl_t.config(image=self.tk_img, text="")
        except: pass

    def update_voice_list(self):
        self.cb['values'] = list(self.app.voice_lib.keys())

    def get_data(self):
        """将卡片所有信息序列化，用于 JSON 存档"""
        return {
            "task_id": self.task_id,
            "prompt": self.txt_p.get("1.0", "end-1c"),
            "script": self.txt_s.get("1.0", "end-1c"),
            "img_path": self.file_path,
            "char": self.cb.get(),
            "motion_key": self.cb_motion.get(),
            "duration": self.cb_dur.get(),
            "ratio": self.cb_ratio.get(),
            # --- 必须包含以下两项，否则 auto_save_all 会丢失分镜数据 ---
            "shot_notes_data": self.saved_shot_data, 
            "is_custom_camera": self.is_custom_camera
        }
        #return data
    

    def start(self):
        if not self.file_path:
            messagebox.showwarning("提示", "请先选择图片"); return
        if self.is_running: return

        self.is_running = True
        self.btn.config(state="disabled", text="⏳ 运行中")
        
        # 1. 在【主线程】启动计时器
        self.start_timer_ui()
        
        # 2. 在【子线程】启动业务逻辑
        threading.Thread(target=self.work, daemon=True).start()


    def start_timer_ui(self):
        """由主线程驱动的 UI 刷新器"""
        start_t = time.time()
        
        def tick():
            # 只要任务还在跑，且卡片没被删，就继续计秒
            if self.is_running and self.app.find_task_by_id(self.task_id):
                try:
                    if self.lbl_tm.winfo_exists():
                        elapsed = int(time.time() - start_t)
                        m, s = divmod(elapsed, 60)
                        self.lbl_tm.config(text=f"{m:02d}:{s:02d}")
                        
                        # 解决 EXE 恢复后锁定的关键补丁
                        # 强制主线程处理积压的 UI 任务
                        self.app.root.update_idletasks()
                        
                        self.app.root.after(1000, tick)
                except:
                    pass
        tick()
    # --- 在 TaskCard 类内部添加 ---

    def safe_update_status(self, text, foreground="black"):
        """安全更新 UI，如果卡片已被删则停止线程"""
        def _update():
            try:
                # 检查组件是否还存在
                if self.frame.winfo_exists():
                    self.lbl_st.config(text=text, foreground=foreground)
            except:
                pass

        # 1. 检查 ID 是否还在活跃映射中
        if self.app.find_task_by_id(self.task_id):
            self.app.root.after(0, _update)
        else:
            # 2. 如果卡片不在了，标志位设为 False，后台线程会在下一个循环停止
            print(f"DEBUG: 任务 {self.task_id} 已从映射中移除，线程将停止。")
            self.is_running = False

    def work(self):
        """
        运行在子线程：负责核心业务逻辑（API请求、排队等）。
        不再包含 tick 计时器，计时器由主线程独立维护。
        """
        blacklist = []
        max_activate_retries = 3
        final_prompt_text = self.get_final_prompt()
        print(final_prompt_text)
        # --- 核心排队循环 ---
        try:
            while self.is_running:
                # 1. 获取资源
                res = self.app.res_manager.acquire_key(blacklist)
                
                # 判断 acquire_key 为何返回
                if res is None: 
                    # 只有当 self.app.stop_queue_signal 为 True 时才会返回 None
                    self.safe_update_status(text="🛑 已停止排队", foreground="orange")
                    break
                
                # 2. 拿到可用 Key，更新 UI 负载
                try:
                    self.safe_update_status(text=f"📡 激活中({res['label']})...", foreground="blue")
                    # 使用 after(0) 确保跨线程调用 UI 更新是安全的
                    self.app.root.after(0, self.app.update_monitor)
                    
                    # 3. 尝试提交以获取 taskId
                    submit_res = self._submit_to_server(res['key'])
                    
                    if submit_res.get("code") == 0:
                        task_id = submit_res["data"]["taskId"]
                        # 进入远程轮询阶段
                        # 注意：_run_remote_polling 内部逻辑应在完成后自行 return 或 release_key
                        self._run_remote_polling(task_id, res)
                        break # 任务成功开始/结束，跳出排队循环
                    else:
                        # 提交失败处理
                        print(f"❌ 激活失败: {submit_res.get('msg')}")
                        blacklist.append(res['key'])
                        self.app.res_manager.release_key(res['key'])
                        self.app.root.after(0, self.app.update_monitor)
                        
                        if len(blacklist) >= max_activate_retries:
                            self.safe_update_status(text="❌ 多次激活失败", foreground="red")
                            break
                        time.sleep(1) # 短暂等待重试

                except Exception as e:
                    print(f"⚠️ 调度异常: {e}")
                    if res: 
                        self.app.res_manager.release_key(res['key'])
                        self.app.root.after(0, self.app.update_monitor)
                    break
        
        finally:
            # 统一出口：无论任务成功、失败还是中止，都必须重置状态
            self.is_running = False
            # 恢复按钮状态（必须回到主线程操作）
            self.app.root.after(0, self._reset_ui_state)

    def _reset_ui_state(self):
        """辅助函数：在主线程恢复 UI 初始状态"""
        self.btn.config(state="normal", text="▶ 运行")

    def _submit_to_server(self, api_key):
        """封装具体的提交请求参数"""
        api_seconds = int(self.dur_map.get(self.cb_dur.get(), "10s").replace('s',''))
        api_model = self.ratio_map.get(self.cb_ratio.get(), "landscape")
        return runninghub.submit_task_all(
            webapp_id=self.app.web_appid.get(),
            API_KEY=api_key,
            file_path=self.file_path,
            SysPrompt=self.app.sys_prompt.get(),
            prompt=self.get_final_prompt(),
            duration_seconds=api_seconds,
            model_type=api_model
        )

    def _run_remote_polling(self, task_id, key_res):
        """阶段二：远程执行监控。"""
        start_wait_time = time.time()
        timeout = 1200 
        api_key = key_res['key']

        try:
            while self.is_running: # [优化] 增加 self.is_running 检查
                try:
                    outputs_result = runninghub.query_task_outputs(task_id, api_key)
                except Exception as net_err:
                    print(f"📡 网络波动中 (10s后重试): {net_err}")
                    time.sleep(10)
                    continue

                code = outputs_result.get("code")
                data = outputs_result.get("data")

                if code == 0 and data:
                    video_url = data[0].get("fileUrl")
                    self._handle_download(video_url)
                    self.safe_update_status(text="✅ 处理完成", foreground="green")
                    break
                elif code in [804, 813]:
                    status_text = "运行中" if code == 804 else "云端排队"
                    self.safe_update_status(text=f"⏳ {status_text}...", foreground="#0078d4")
                elif code == 805:
                    # [优化] 增强健壮性的 data 检查
                    reason = data.get("failedReason") if isinstance(data, dict) else "节点计算失败"
                    self.safe_update_status(text="❌ 生成失败", foreground="red")
                    print(f"❌ 云端任务失败: {reason}")
                    break
                else:
                    # 此时可能是 401(Key失效) 或其他未知 code
                    raise Exception(f"接口返回异常 code:{code} msg:{outputs_result.get('msg')}")

                # 检查超时
                if time.time() - start_wait_time > timeout:
                    raise Exception("云端渲染超时")
                
                # [优化] 将 8s 长睡拆解为小步长，支持秒级取消响应
                for _ in range(8):
                    if not self.is_running: break
                    time.sleep(1)

        except Exception as e:
            print(f"❌ 执行期异常: {e}")
            self.safe_update_status(text="❌ 任务中断", foreground="red")
        finally:
            # 无论如何释放资源
            self.app.res_manager.release_key(api_key)
            self.app.update_monitor()
            self.is_running = False # 确保线程状态同步

    def _handle_download(self, video_url):
        """封装下载保存逻辑"""
        self.safe_update_status(text="📥 正在下载...", foreground="purple")
        target_dir = self.app.save_dir.get()
        if not os.path.exists(target_dir): os.makedirs(target_dir)
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        
        if core_logic.VideoDownloader.download(video_url, target_dir, filename):
            self.safe_update_status(text="✅ 完成并保存", foreground="green")
        else:
            self.safe_update_status(text="❌ 保存失败", foreground="red")

class ActionManager:
    def __init__(self, app):
        self.app = app
        self.undo_stack = []
        self.redo_stack = []
        self.max_depth = 30

    def push_action(self, action_type, payload):
        """记录一个新动作"""
        action = {"type": action_type, "payload": payload}
        self.undo_stack.append(action)
        if len(self.undo_stack) > self.max_depth:
            self.undo_stack.pop(0)
        self.redo_stack.clear() # 有新动作，清空重做栈



    def undo(self, event=None):
        # 1. 撤销前强制结算：如果用户正在打字，先存入当前内容
        focus_w = self.app.root.focus_get()
        if isinstance(focus_w, tk.Text) and hasattr(focus_w, "parent_card"):
            focus_w.parent_card.force_settle()

        # 2. 标准撤销逻辑
        if not self.undo_stack: return
        action = self.undo_stack.pop()
        self.redo_stack.append(action)
        self._dispatch(action, mode="UNDO")

    # 关键修改：添加 event=None
    def redo(self, event=None):
    # 1. 重做前同样强制结算当前正在打字的内容
        focus_w = self.app.root.focus_get()
        if isinstance(focus_w, tk.Text) and hasattr(focus_w, "parent_card"):
            focus_w.parent_card.force_settle()

        # 2. 执行重做逻辑
        if not self.redo_stack: return
        action = self.redo_stack.pop()
        self.undo_stack.append(action)
        self._dispatch(action, mode="REDO")

    def _dispatch(self, action, mode="UNDO"):
        """
        核心分发器：执行具体的 UI 撤销/重做操作。
        已修复：处理 BATCH_DEL 时列表对象无 .get() 的问题。
        """
        a_type = action["type"]
        p = action["payload"]

        # --- 1. 运行状态安全检查 ---
        # 针对批量删除的特殊处理
        if a_type == "BATCH_DEL":
            if mode == "REDO":
                # 检查这批卡片里有没有人在运行
                # p 是列表，所以要遍历检查
                if any(self.app.task_mapping.get(item["task_id"]).is_running 
                    for item in p if self.app.task_mapping.get(item["task_id"])):
                    print("DEBUG: 批量重做删除被拦截 - 包含运行中的卡片")
                    return
        else:
            # 针对单张卡片操作的检查（ADD_CARD, DEL_CARD, EDIT_TEXT）
            target_id = p.get("task_id") if isinstance(p, dict) else None
            target_card = self.app.task_mapping.get(target_id)

            if target_card and target_card.is_running:
                is_undo_add = (a_type == "ADD_CARD" and mode == "UNDO")
                is_redo_del = (a_type == "DEL_CARD" and mode == "REDO")
                is_edit = (a_type == "EDIT_TEXT")
                if is_undo_add or is_redo_del or is_edit:
                    print(f"DEBUG: 动作 {a_type} 被拦截 - 卡片正在运行")
                    return

        # --- 2. 具体执行逻辑 ---
        if a_type == "ADD_CARD":
            if mode == "UNDO":
                self.app.destroy_card_by_id(p["task_id"], record=False)
            else:
                self.app.add_task_card(p["data"], is_redo_op=True)

        elif a_type == "DEL_CARD":
            if mode == "UNDO":
                new_card = self.app.add_task_card(p["data"], is_undo_op=True)
                new_card.is_running = False
                if new_card in self.app.tasks:
                    self.app.tasks.remove(new_card)
                self.app.tasks.insert(p["index"], new_card)
                self.app.refresh_ui_layout()
            else:
                self.app.destroy_card_by_id(p["task_id"], record=False)

        elif a_type == "BATCH_DEL":
            if mode == "UNDO":
                # 撤销删除：复活多张卡片
                sorted_payload = sorted(p, key=lambda x: x["index"])
                for item in sorted_payload:
                    new_card = self.app.add_task_card(item["data"], is_undo_op=True)
                    if new_card in self.app.tasks:
                        self.app.tasks.remove(new_card)
                    self.app.tasks.insert(item["index"], new_card)
                self.app.refresh_ui_layout()
            else:
                # 重做删除：批量物理切除
                for item in p:
                    self.app.destroy_card_by_id(item["task_id"], record=False)

        elif a_type == "EDIT_TEXT":
            card = self.app.task_mapping.get(p["task_id"])
            if card:
                target_val = p["old_val"] if mode == "UNDO" else p["new_val"]
                card.set_text_silent(p["field"], target_val)
                self.app.auto_save_all()
        
        elif a_type == "EDIT_SHOTS":
            card = self.app.task_mapping.get(p["task_id"])
            if card:
                # 根据 UNDO 或 REDO 选择对应的快照数据
                target_data = p["old_data"] if mode == "UNDO" else p["new_data"]
                target_custom = p["old_custom"] if mode == "UNDO" else p["new_custom"]
                
                # 静默更新卡片数据（不触发重复记录）
                card.saved_shot_data = target_data
                card.is_custom_camera = target_custom
                
                # 更新 UI 按钮状态
                card._update_editor_btn_style()
                # 触发保存
                self.app.auto_save_all()
# --- 4. 主程序 ---
class VideoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("2.0 -DirectorEditor table")
        self.root.geometry("1100x850")
        
        # --- 1. 数据与资源初始化 ---
        self.all_data = core_logic.DataIO.load_json("config_and_history.json", {})
        
        # API 与系统参数
        self.web_appid = tk.StringVar(value="1973465795936260097")
        self.sys_prompt = tk.StringVar(value=self.all_data.get("sys_prompt", ""))
        self.custom_motions = self.all_data.get("custom_motions", {})
        
        saved_path = self.all_data.get("save_path")
        if not saved_path: 
            saved_path = os.path.join(os.getcwd(), "downloads")
        self.save_dir = tk.StringVar(value=saved_path)

        self.api_pool = self.all_data.get("api_pool", [])
        self.voice_lib = self.all_data.get("voices", {})
        self.res_manager = core_logic.ResourceManager(self, self.api_pool)
        self.stop_queue_signal = False
        
        # --- 2. 核心数据结构 ---
        self.tasks = []           # 列表：管理 UI 物理顺序
        self.task_mapping = {}    # 映射表：{task_id: card_instance} 解决膨胀关键
        
        # --- 3. 撤销经理初始化 ---
        # 废弃直接操作 undo_stack，改用经理类
        self.action_manager = ActionManager(self)

        # --- 4. UI 初始化 ---
        self.setup_menu()
        self.setup_ui()
        
        # 只有在加载历史时，不产生撤销记录
        self.load_history()

        # --- 5. 绑定全局快捷键 ---
        # 绑定到经理类的方法上
        self.root.bind("<Control-z>", self.action_manager.undo)
        self.root.bind("<Control-Z>", self.action_manager.undo)
        self.root.bind("<Control-y>", self.action_manager.redo)
        self.root.bind("<Control-Y>", self.action_manager.redo)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.root.bind("<FocusIn>", lambda e: self.root.update())
        self.root.bind("<Map>", lambda e: self.root.update_idletasks())
        # 【修复说明】：删除了 self.undo_stack.append(self._get_current_snapshot())
        # 因为在 Action-based 逻辑下，初始状态不需要占位，否则撤销第一步会报错。
        self.root.bind("<Map>", self._force_refresh_on_restore)

    def _force_refresh_on_restore(self, event):
        """当窗口从任务栏恢复时，强制刷新所有组件"""
        try:
            self.root.update_idletasks()
            for task in self.tasks:
                if task.is_running:
                    # 重新计算一次时间，纠正可能的显示偏差
                    task.refresh_ui_layout() # 或者你自定义的轻量刷新
        except:
            pass
    # --- 撤销/重做核心逻辑 ---

    def find_task_by_id(self, task_id):
        """【新增】通过 ID 快速找回卡片对象"""
        return self.task_mapping.get(task_id)

    def remove_task_reference(self, task_id):
        """【新增】物理删除卡片时，清理映射关系，防止内存泄漏"""
        if task_id in self.task_mapping:
            del self.task_mapping[task_id]
        
    def global_undo(self, event=None):
        focus_w = self.root.focus_get()
        # 依然保留对 Text 组件自带撤销的支持
        if isinstance(focus_w, tk.Text):
            try:
                focus_w.edit_undo()
                return "break"
            except Exception: pass
        
        # 调用新经理
        self.action_manager.undo()
        return "break"

    def global_redo(self, event=None):
        focus_w = self.root.focus_get()
        if isinstance(focus_w, tk.Text):
            try:
                focus_w.edit_redo()
                return "break"
            except Exception: pass
            
        self.action_manager.redo()
        return "break"


        # --- 镜头管理增强逻辑 ---

    def refresh_all_tasks_motion(self):
        """当镜头预设库发生变动时，静默刷新所有卡片的下拉列表内容"""
        for task in self.tasks:
            if hasattr(task, 'update_motion_list'):
                task.update_motion_list()

    def open_motion_editor(self):
        """弹出自定义镜头 Prompt 管理器"""
        # 这里需要引用我们之前定义的 MotionPresetEditor 类
        MotionPresetEditor(self.root, self)
    # --- 2. 基础功能逻辑 ---

    def setup_menu(self):
        m = tk.Menu(self.root)
        
        # --- 1. 全局配置菜单 ---
        c = tk.Menu(m, tearoff=0)
        c.add_command(label="🔑 API Key 池管理", command=lambda: KeyPoolEditor(self.root, self))
        c.add_command(label="🌐 系统提示词配置", command=self.open_webapp_config)
        c.add_command(label="👥 声纹库管理", command=lambda: VoiceTableEditor(self.root, self))
        # 新增：镜头库管理入口
        c.add_command(label="🎬 镜头Prompt库管理", command=self.open_motion_editor)
        
        m.add_cascade(label="⚙️ 全局配置", menu=c)

        # --- 2. 编辑菜单 (撤销/重做/清空) ---
        e = tk.Menu(m, tearoff=0)
        e.add_command(label="↩️ 撤销 (Ctrl+Z)", command=self.global_undo)
        e.add_command(label="↪️ 重做 (Ctrl+Y)", command=self.global_redo)
        e.add_separator()
        e.add_command(label="🗑️ 清空所有任务卡片", command=self.clear_all_tasks)
        
        m.add_cascade(label="🛠️ 编辑", menu=e)

        self.root.config(menu=m)

    def setup_ui(self):
        t = ttk.Frame(self.root, padding=10)
        t.pack(fill=tk.X)
        ttk.Button(t, text="➕ 新建镜头", command=self.add_task_card).pack(side=tk.LEFT, padx=5)
        # --- [新增] 全局默认配置 ---
        ttk.Label(t, text=" 默认:").pack(side=tk.LEFT, padx=(5, 0))
        
        # 比例预设 (从 self.global_presets 读取初始值)
        self.preset_ratio = ttk.Combobox(t, values=[
            "竖屏 (9:16)", "横屏 (16:9)", "竖屏高清", "横屏高清"
        ], width=11, state="readonly")
        # 这里的 "竖屏 (9:16)" 可以根据你的 global_presets 映射逻辑动态设置
        self.preset_ratio.set("竖屏 (9:16)") 
        self.preset_ratio.pack(side=tk.LEFT, padx=2)
        self.preset_dur = ttk.Combobox(t, values=["10秒", "15秒"], width=5, state="readonly")
        self.preset_dur.set("10秒")
        self.preset_dur.pack(side=tk.LEFT, padx=2)
        ttk.Button(t, text="🗑️ 清空所有", command=self.clear_all_tasks).pack(side=tk.LEFT, padx=5)
        ttk.Button(t, text="🛑 中止排队", command=self.stop).pack(side=tk.LEFT, padx=5)
        ttk.Button(t, text="📂 下载目录", command=self.select_download_dir).pack(side=tk.LEFT, padx=5)
        self.btn_save = ttk.Button(t, text="💾 保存全部", command=self.manual_save_trigger)
        self.btn_save.pack(side=tk.LEFT, padx=5)
        self.lbl_m = ttk.Label(t, text="负载: 0", font=("Arial", 10, "bold"))
        self.lbl_m.pack(side=tk.RIGHT)

        self.cv = tk.Canvas(self.root, bg="#f8f9fa")
        self.cv.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(self.root, command=self.cv.yview)
        sb.pack(side="right", fill="y")
        self.sf = tk.Frame(self.cv, bg="#f8f9fa")
        self.cv.create_window((0,0), window=self.sf, anchor="nw", width=1080)
        self.cv.config(yscrollcommand=sb.set)
        self.sf.bind("<Configure>", lambda e: self.cv.config(scrollregion=self.cv.bbox("all")))

    def open_motion_editor(self):
        """主界面菜单或按钮调用的函数"""
        MotionPresetEditor(self.root, self)

    
    def add_task_card(self, data=None, is_undo_op=False, is_redo_op=False):
        """新建或根据数据恢复卡片"""
        is_loading = data is not None 
        
        if data is None:
            # 补全默认字段，特别是 motion_key
            data = {
                "ratio_text": self.preset_ratio.get(),
                "duration_text": self.preset_dur.get(),
                "motion_key": "无",  # 显式提供默认值
                "status": "waiting",
                "prompt": "",
                "script": "",
                "char": "无",
                "img_path": ""
            }
        
        # 1. 创建卡片（确保 TaskCard.__init__ 内部调用了 self.update_motion_list()）
        card = TaskCard(self.sf, self, data=data)
        self.tasks.append(card)
        
        # 2. 映射记录
        if hasattr(card, 'task_id'):
            self.task_mapping[card.task_id] = card

        # 3. 撤销记录逻辑 (保持你原有的不变)
        if not (is_undo_op or is_redo_op or is_loading):
            self.action_manager.push_action("ADD_CARD", {
                "task_id": card.task_id,
                "data": card.get_data() 
            })

        # 4. UI 刷新
        self._refresh_canvas_scroll()
        
        if not is_loading:
            self.cv.yview_moveto(1.0)
            self.auto_save_all()
            
        return card

    

    def destroy_card_by_id(self, task_id, record=True):
        """精准销毁：record=True时记录到撤销栈；自动跳过运行中的卡片"""
        card = self.task_mapping.get(task_id)
        if not card: return

        # --- 【关键修正】运行锁保护 ---
        if card.is_running:
            print(f"DEBUG: 拦截销毁请求 - 卡片 {task_id} 正在任务中，跳过销毁。")
            return 

        # 1. 记录撤销动作
        if record:
            try:
                idx = self.tasks.index(card)
                self.action_manager.push_action("DEL_CARD", {
                    "task_id": task_id,
                    "data": card.get_data(),
                    "index": idx
                })
            except ValueError:
                pass # 防止卡片已不在 tasks 列表中的异常

        # 2. 清理内存引用
        if card in self.tasks: 
            self.tasks.remove(card)
        if task_id in self.task_mapping: 
            del self.task_mapping[task_id]
        
        # 3. 物理销毁 UI 组件
        if card.frame.winfo_exists():
            card.frame.destroy()
        
        # 4. 刷新 UI 容器布局
        # 确保在 destroy 后刷新，Canvas 才能正确计算剩余卡片的高度
        self.root.after(10, self._refresh_canvas_scroll) # 延迟一小下确保组件已彻底销毁
        
        # 5. 系统状态同步
        self.update_monitor()
        self.auto_save_all()

    def _refresh_canvas_scroll(self):
        """提取出的排版刷新逻辑"""
        self.sf.update_idletasks()
        self.cv.config(scrollregion=self.cv.bbox("all"))

    def refresh_ui_layout(self):
        """重新排版所有卡片（撤销删除插回原位后必须调用）"""
        for card in self.tasks:
            card.frame.pack_forget()
            card.frame.pack(fill=tk.X, padx=15, pady=8)
        self.cv.config(scrollregion=self.cv.bbox("all"))


    

    def clear_all_tasks(self):
        from tkinter import messagebox
        if not self.tasks: return

        msg = ("请选择要删除的范围：\n\n"
            "【是】：删除所有已停止的任务\n"
            "【否】：仅删除未请求（就绪）的任务\n"
            "【取消】：放弃\n\n"
            "提示：一次 Ctrl+Z 即可全部找回。")
        
        choice = messagebox.askyesnocancel("批量删除", msg)
        if choice is None: return

        # 1. 筛选待删列表
        to_delete = []
        for task in self.tasks:
            if task.is_running: continue
            status_text = task.lbl_st.cget("text")
            if choice is True or (choice is False and status_text == "就绪"):
                to_delete.append(task)

        if not to_delete: return

        # 2. 构造批量数据包
        batch_data = []
        for task in to_delete:
            batch_data.append({
                "index": self.tasks.index(task),
                "data": task.get_data(),
                "task_id": task.task_id
            })

        # 3. 记录到撤销经理 (记录一次 BATCH_DEL)
        self.action_manager.push_action("BATCH_DEL", batch_data)

        # 4. 执行物理删除 (此时 record=False，因为我们已经手动打包记录了)
        for task in to_delete:
            self.destroy_card_by_id(task.task_id, record=False)

    def on_closing(self):
        self.auto_save_all()
        self.root.destroy()

    def auto_save_all(self):
        try:
            history = []
            for t in self.tasks:
                # 只有存在的卡片才存，通过 get_data() 获取最准，或者手动提取
                if t.frame.winfo_exists():
                    history.append(t.get_data()) # 推荐在 TaskCard 里实现 get_data
            full_config = {
            "web_appid": self.web_appid.get(),
            "sys_prompt": self.sys_prompt.get(),
            "save_path": self.save_dir.get(),
            "api_pool": self.api_pool,
            "voices": self.voice_lib,
            "custom_motions": self.custom_motions, # 保存自定义镜头库
            "history": history
        }
            core_logic.DataIO.save_json("config_and_history.json", full_config)
        except Exception as e: print(f"Save Error: {e}")


    def refresh_all_cards_motion(self):
        for task in self.tasks:
            task.update_motion_list()

    def load_history(self):
        # 1. 尝试从全量 history 字段读取（这是你 auto_save_all 存的地方）
        history_data = self.all_data.get("history", [])
        
        # 如果 history 为空，再尝试看旧版的 task_history
        if not history_data:
            history_data = self.all_data.get("task_history", [])

        if history_data:
            for data in history_data:
                # is_undo_op=True 可以防止加载历史时弹出“新建”提示
                self.add_task_card(data, is_undo_op=True) 
        else:
            # 只有真正没有任何数据时，才创建一个空白卡片
            self.add_task_card()

    #def stop(self): self.stop_queue_signal = True
    def stop(self):
        """用户点击‘停止所有排队’按钮"""
        self.stop_queue_signal = True
        
        # 核心：唤醒 ResourceManager 中所有正在排队的线程
        if hasattr(self, 'res_manager'):
            with self.res_manager.cv:
                self.res_manager.cv.notify_all()
                
        print("✅ 信号已发送：正在排队的任务将取消，运行中的任务将继续完成。")
      

    def select_download_dir(self):
        path = filedialog.askdirectory()
        if path: self.save_dir.set(path); self.auto_save_all()
    def manual_save_trigger(self):
        self.auto_save_all()
        self.btn_save.config(text="✅ 已存入JSON")
        self.root.after(1500, lambda: self.btn_save.config(text="💾 保存全部"))
    def update_monitor(self):
        """更新 UI 顶部的总负载显示"""
        if hasattr(self, 'res_manager'):
            # 计算所有 Key 实体的当前活跃任务总数
            total_load = sum(entity.current_active for entity in self.res_manager.key_entities)
            self.lbl_m.config(text=f"负载: {total_load}")

    def open_webapp_config(self):
        win = tk.Toplevel(self.root)
        win.title("全局配置")
        win.geometry("450x350") # 稍微调小高度，因为少了一项

        # 【已移除】RunningHub Web AppID 的 Entry

        ttk.Label(win, text="全局系统提示词 (Sys Prompt):").pack(pady=10)
        txt = tk.Text(win, height=8, width=45)
        txt.pack(pady=5)
        txt.insert("1.0", self.sys_prompt.get())

        ttk.Label(win, text="默认导出目录:").pack(pady=5)
        f = ttk.Frame(win); f.pack()
        tk.Entry(f, textvariable=self.save_dir, width=30).pack(side=tk.LEFT)
        ttk.Button(f, text="浏览", command=lambda: self.save_dir.set(filedialog.askdirectory())).pack(side=tk.LEFT)

        def save_close():
            self.sys_prompt.set(txt.get("1.0", tk.END).strip())
            # 注意：auto_save_all 依然会运行，但它保存的是你代码里硬编码的值
            self.auto_save_all()
            win.destroy()
            
        ttk.Button(win, text="保存并同步", command=save_close).pack(pady=20)

# --- main_ui.py ---
class MotionPresetEditor:
    def __init__(self, parent, app):
        self.app = app
        self.win = tk.Toplevel(parent)
        self.win.title("🎬 自定义镜头库管理")
        self.win.geometry("800x500")
        self.win.grab_set()

        # --- 布局：左侧列表，右侧编辑 ---
        main_f = ttk.Frame(self.win, padding=10)
        main_f.pack(fill=tk.BOTH, expand=True)

        # 左侧列表框
        left_f = ttk.Frame(main_f)
        left_f.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        ttk.Label(left_f, text="已保存的预设:").pack(anchor=tk.W)
        self.listbox = tk.Listbox(left_f, font=("微软雅黑", 10))
        self.listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self.listbox.bind("<<ListboxSelect>>", self.load_selected)

        # 右侧表单
        right_f = ttk.Frame(main_f, padding=(10, 0))
        right_f.pack(side=tk.RIGHT, fill=tk.BOTH)

        ttk.Label(right_f, text="名称 (如: 侧颜滑移):").pack(anchor=tk.W)
        self.ent_name = ttk.Entry(right_f, width=30)
        self.ent_name.pack(fill=tk.X, pady=5)

        ttk.Label(right_f, text="镜头模式 (如: 平移):").pack(anchor=tk.W)
        self.ent_mode = ttk.Entry(right_f, width=30)
        self.ent_mode.pack(fill=tk.X, pady=5)

        ttk.Label(right_f, text="Prompt 词 (英文):").pack(anchor=tk.W)
        self.txt_prompt = tk.Text(right_f, width=30, height=5, font=("Consolas", 9))
        self.txt_prompt.pack(fill=tk.X, pady=5)

        ttk.Label(right_f, text="场景/用例描述 (中文):").pack(anchor=tk.W)
        self.txt_example = tk.Text(right_f, width=30, height=5, font=("微软雅黑", 9))
        self.txt_example.pack(fill=tk.X, pady=5)

        # 按钮区
        btn_f = ttk.Frame(right_f)
        btn_f.pack(fill=tk.X, pady=10)
        ttk.Button(btn_f, text="保存/更新", command=self.save_preset).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_f, text="删除选中", command=self.delete_preset).pack(side=tk.LEFT, padx=2)

        self.refresh_list()

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        # 仅显示自定义的镜头
        for name in self.app.custom_motions.keys():
            self.listbox.insert(tk.END, name)

    def load_selected(self, event):
        sel = self.listbox.curselection()
        if not sel: return
        name = self.listbox.get(sel[0])
        data = self.app.custom_motions.get(name)
        if data:
            self.ent_name.delete(0, tk.END)
            self.ent_name.insert(0, name)
            self.ent_mode.delete(0, tk.END)
            self.ent_mode.insert(0, data.get("mode", ""))
            self.txt_prompt.delete("1.0", tk.END)
            self.txt_prompt.insert("1.0", data.get("prompt", ""))
            self.txt_example.delete("1.0", tk.END)
            self.txt_example.insert("1.0", data.get("example", ""))

    def save_preset(self):
        name = self.ent_name.get().strip()
        if not name: return
        
        # 构造存储结构，保持与 MOTION_LIBRARY 一致
        self.app.custom_motions[name] = {
            "name": name,
            "mode": self.ent_mode.get().strip(),
            "prompt": self.txt_prompt.get("1.0", tk.END).strip(),
            "example": self.txt_example.get("1.0", tk.END).strip(),
            "tags": [name] # 默认把名称作为搜索标签
        }
        self.app.auto_save_all()
        self.refresh_list()
        self.app.refresh_all_tasks_motion() # 通知所有卡片更新下拉框

    def delete_preset(self):
        sel = self.listbox.curselection()
        if not sel: return
        name = self.listbox.get(sel[0])
        if messagebox.askyesno("确认", f"删除预设 {name}？"):
            del self.app.custom_motions[name]
            self.app.auto_save_all()
            self.refresh_list()
            self.app.refresh_all_tasks_motion()


class MotionSearcher:
    def __init__(self, parent, app, on_select_callback):
        self.win = tk.Toplevel(parent)
        self.app = app  # 确保传入 app 实例以读取 custom_motions
        self.win.title("🎬 镜头运动搜索与场景匹配")
        self.win.geometry("700x550")
        self.win.grab_set()  # 模态窗口
        self.callback = on_select_callback

        # --- 1. 搜索区域 ---
        search_f = ttk.Frame(self.win, padding=10)
        search_f.pack(fill=tk.X)
        
        ttk.Label(search_f, text="🔍 搜索意图:", font=("微软雅黑", 10, "bold")).pack(side=tk.LEFT)
        self.ent_search = ttk.Entry(search_f, font=("微软雅黑", 10))
        self.ent_search.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        self.ent_search.focus_set()
        
        # 实时搜索绑定
        self.ent_search.bind("<KeyRelease>", self.do_search)

        # --- 2. 结果列表 ---
        list_f = ttk.Frame(self.win, padding=10)
        list_f.pack(fill=tk.BOTH, expand=True)

        columns = ("name", "mode", "tags")
        self.tree = ttk.Treeview(list_f, columns=columns, show="headings", height=10)
        self.tree.heading("name", text="方案名称")
        self.tree.heading("mode", text="镜头模式")
        self.tree.heading("tags", text="匹配关键词")
        
        self.tree.column("name", width=120, anchor=tk.CENTER)
        self.tree.column("mode", width=120, anchor=tk.CENTER)
        self.tree.column("tags", width=350)
        
        sb = ttk.Scrollbar(list_f, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=sb.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<<TreeviewSelect>>", self.on_item_select)
        self.tree.bind("<Double-1>", self.confirm_selection)

        # --- 3. 详情与用例预览区 ---
        self.detail_f = ttk.LabelFrame(self.win, text=" 效果详情与推荐场景预览 ", padding=15)
        self.detail_f.pack(fill=tk.X, padx=15, pady=15)

        self.info_var = tk.StringVar(value="请从上方列表中选择或搜索一个动态效果...")
        self.lbl_info = ttk.Label(self.detail_f, textvariable=self.info_var, 
                                 wraplength=600, justify=tk.LEFT, font=("微软雅黑", 9))
        self.lbl_info.pack(fill=tk.X)

        # 初始化加载：使用合并后的库
        self.refresh_table(self.get_full_lib())

    def get_full_lib(self):
        """核心修改：动态合并内置库和用户自定义库"""
        # 获取内置库副本
        full_lib = list(core_logic.MOTION_LIBRARY)
        # 获取自定义库并转为列表
        if hasattr(self.app, 'custom_motions'):
            custom_list = list(self.app.custom_motions.values())
            full_lib.extend(custom_list)
        return full_lib

    def do_search(self, event):
        query = self.ent_search.get().strip().lower()
        all_motions = self.get_full_lib() # 搜索时也基于全库
        
        if not query:
            self.refresh_table(all_motions)
            return

        # 匹配逻辑：名称、模式或标签中包含关键字
        filtered = [
            item for item in all_motions
            if query in item["name"].lower() or 
               query in item.get("mode", "").lower() or 
               any(query in t.lower() for t in item.get("tags", []))
        ]
        self.refresh_table(filtered)

    def refresh_table(self, data):
        self.tree.delete(*self.tree.get_children())
        for item in data:
            # 兼容处理：确保即使 tags 不存在也不报错
            tags_str = " / ".join(item.get("tags", []))
            self.tree.insert("", "end", values=(item["name"], item.get("mode", "未定义"), tags_str))

    def on_item_select(self, event):
        sel = self.tree.selection()
        if not sel: return
        name = self.tree.item(sel[0], "values")[0]
        
        # 从全库查找数据
        all_motions = self.get_full_lib()
        data = next((i for i in all_motions if i["name"] == name), None)
        
        if data:
            detail_text = f"【镜头模式】: {data.get('mode', '未定义')}\n\n"
            detail_text += f"【场景用例】: {data.get('example', '暂无描述')}"
            self.info_var.set(detail_text)

    def confirm_selection(self, event):
        sel = self.tree.selection()
        if not sel: return
        name = self.tree.item(sel[0], "values")[0]
        self.callback(name) 
        self.win.destroy()

if __name__ == "__main__":
    root = tk.Tk(); app = VideoApp(root); root.mainloop()