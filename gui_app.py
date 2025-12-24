import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import threading
import time
import os
import re
from datetime import datetime
import core_logic

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
        self.data = data if data else {}
        self.frame = ttk.LabelFrame(parent, text=" 镜头卡片 ", padding=10)
        self.frame.pack(fill=tk.X, padx=15, pady=8)
        self.file_path = self.data.get("img_path", "")
        self.is_running = False
        self.setup_ui()
        if self.file_path: self.load_thumbnail(self.file_path)

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
        self.txt_p = tk.Text(mid, height=3, font=("微软雅黑", 9), undo=True, autoseparators=True)
        self.txt_p.pack(fill=tk.X, pady=(0, 5))
        self.txt_p.insert("1.0", self.data.get("prompt", ""))
        self.txt_p.bind("<FocusOut>", lambda e: self.app.auto_save_all())

        # --- 台词内容区 ---
        ttk.Label(mid, text="台词内容:", font=("微软雅黑", 9, "bold")).pack(anchor=tk.W)
        self.txt_s = tk.Text(mid, height=1, font=("微软雅黑", 9, "bold"), undo=True, autoseparators=True)
        self.txt_s.pack(fill=tk.X, pady=(0, 5))
        self.txt_s.insert("1.0", self.data.get("script", ""))
        self.txt_s.bind("<FocusOut>", lambda e: self.app.auto_save_all())

        # --- 控制行 ---
        ctrl = tk.Frame(mid) 
        ctrl.pack(fill=tk.X)
        
        # 1. 动态指令选择
        ttk.Label(ctrl, text="动态:").pack(side=tk.LEFT)
        self.cb_motion = ttk.Combobox(ctrl, state="readonly", width=10)
        self.cb_motion.pack(side=tk.LEFT, padx=2)
        
        # 【新增】搜索匹配按钮：点击打开可视化搜索手册
        self.btn_motion_search = ttk.Button(
            ctrl, 
            text="🔍", 
            width=3, 
            # 错误写法：lambda: MotionSearcher(self.app.root, self.set_motion_by_name)
            # 正确写法：必须传入 self.app 实例
            command=lambda: MotionSearcher(self.app.root, self.app, self.set_motion_by_name)
        )
        self.btn_motion_search.pack(side=tk.LEFT, padx=(0, 5))

        self.update_motion_list() # 初始化列表加载存档
        self.cb_motion.bind("<<ComboboxSelected>>", lambda e: self.app.auto_save_all())
        
        # 2. 角色选择
        ttk.Label(ctrl, text="角色:").pack(side=tk.LEFT)
        self.cb = ttk.Combobox(ctrl, state="readonly", width=8)
        self.update_voice_list()
        self.cb.pack(side=tk.LEFT, padx=2)
        if self.data.get("char"): self.cb.set(self.data["char"])
        self.cb.bind("<<ComboboxSelected>>", lambda e: self.app.auto_save_all())

# --- 3. 比例选择 (修改后的逻辑) ---
        ttk.Label(ctrl, text="比例:").pack(side=tk.LEFT)
        self.cb_ratio = ttk.Combobox(ctrl, values=list(self.ratio_map.keys()), width=12, state="readonly")
        
        # [逻辑优化]：
        # 1. 优先尝试获取 ratio_text (对应我们刚加的全局预设)
        # 2. 其次尝试获取旧版数据 ratio (对应历史记录)
        # 3. 最后给个兜底值
        ratio_text_preset = self.data.get("ratio_text")
        if ratio_text_preset:
            self.cb_ratio.set(ratio_text_preset)
        else:
            saved_ratio_key = self.data.get("ratio", "landscape") # 旧的 key
            self.cb_ratio.set(self.ratio_rev_map.get(saved_ratio_key, "横屏 (16:9)"))
            
        self.cb_ratio.pack(side=tk.LEFT, padx=2)
        self.cb_ratio.bind("<<ComboboxSelected>>", lambda e: self.app.auto_save_all())


   # --- 4. 时长选择 (同样的逻辑) ---
        ttk.Label(ctrl, text="时长:").pack(side=tk.LEFT)
        self.cb_dur = ttk.Combobox(ctrl, values=list(self.dur_map.keys()), width=6, state="readonly")
        
        dur_text_preset = self.data.get("duration_text")
        if dur_text_preset:
            self.cb_dur.set(dur_text_preset)
        else:
            saved_dur_key = self.data.get("duration", "10s")
            self.cb_dur.set(self.dur_rev_map.get(saved_dur_key, "10秒"))
            
        self.cb_dur.pack(side=tk.LEFT, padx=2)
        self.cb_dur.bind("<<ComboboxSelected>>", lambda e: self.app.auto_save_all())
        
        # 5. 运行按钮与状态显示
        self.btn = ttk.Button(ctrl, text="▶ 运行", command=self.start)
        self.btn.pack(side=tk.LEFT, padx=5)
        
        self.lbl_st = ttk.Label(ctrl, text="就绪", foreground="gray")
        self.lbl_st.pack(side=tk.LEFT)
        
        self.lbl_tm = ttk.Label(ctrl, text="00:00")
        self.lbl_tm.pack(side=tk.RIGHT)

    
    def set_motion_by_name(self, name):
        """供 MotionSearcher 调用的回调，实现静默设置"""
        self.cb_motion.set(name)
        self.app.auto_save_all()


    def update_motion_list(self):
        """刷新动态下拉列表（含内置和自定义）"""
        # "无" 表示不添加任何镜头描述
        all_keys = ["无"] + list(core_logic.DEFAULT_MOTIONS.keys()) + list(self.app.custom_motions.keys())
        self.cb_motion['values'] = all_keys
        
        # 恢复存档数据
        saved_key = self.data.get("motion_key", "无")
        if saved_key in all_keys:
            self.cb_motion.set(saved_key)
            self.update_motion_preview(saved_key)
        else:
            self.cb_motion.set("无")
            self.update_motion_preview("无")

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
        结构化集成：将 角色描述 + 用户提示词 + 动态指令 + 台词内容 融为一体
        """
        # 1. 获取界面上的各项原始值
        user_p = self.txt_p.get("1.0", tk.END).strip()      # 用户输入的描述
        script_text = self.txt_s.get("1.0", tk.END).strip() # 台词框内容
        char_name = self.cb.get()                            # 下拉框选中的角色名
        motion_key = self.cb_motion.get()                   # 下拉框选中的镜头名

        # 2. 从声纹库提取该角色的“人设描述”
        char_desc = ""
        if char_name and char_name in self.app.voice_lib:
            char_data = self.app.voice_lib[char_name]
            # 兼容处理：支持你之前存的字典格式 {"desc": "...", "v_id": "..."}
            if isinstance(char_data, dict):
                char_desc = char_data.get("desc", "")
            else:
                char_desc = str(char_data) # 如果是旧的字符串格式也支持

        # 3. 提取镜头动态描述
        full_motion_lib = {**core_logic.DEFAULT_MOTIONS, **self.app.custom_motions}
        motion_p = full_motion_lib.get(motion_key, "") if motion_key != "无" else ""

        # 4. 组合最终 Prompt
        # 建议结构：[人设背景] + [用户场景描述] + [镜头轨迹] + [语音同步引导]
        final_components = []
        

            
        if user_p:
            final_components.append(user_p)
        

            
        if motion_p:
            final_components.append(motion_p)
            
        if script_text:
            # 这一步最关键：把台词内容塞进 Prompt，告诉 AI 角色正在说什么
            final_components.append(f"speaking the lines: '{script_text}', with natural lip-sync")
        
        if char_desc:
            final_components.append(f"Character({char_desc})")

        # 5. 用逗号合并
        final_p = ", ".join(final_components)
        
        # 打印调试信息，你可以在控制台看到最后发给 API 的到底是什么
        print(f"--- 最终集成 Prompt ---\n{final_p}\n-----------------------")
        
        return final_p

    # --- 以下为功能方法保持不变 ---

    def select_file(self):
        p = filedialog.askopenfilename()
        if p: self.file_path = p; self.load_thumbnail(p); self.app.auto_save_all()

    def delete_card(self):
        if messagebox.askyesno("删除", "确定删除？"):
            self.app.record_structure_change()
            self.delete_card_clean()
            if self in self.app.tasks: self.app.tasks.remove(self)
            self.app.auto_save_all()

# TaskCard 内部建议的清理函数
    def delete_card_clean(self):
        self.is_running = False  # 强制终止线程循环
        try:
            self.frame.destroy()
        except:
            pass
        if self in self.app.tasks:
            self.app.tasks.remove(self)

    def load_thumbnail(self, p):
        try:
            img = Image.open(p); img.thumbnail((120, 120))
            self.tk_img = ImageTk.PhotoImage(img)
            self.lbl_t.config(image=self.tk_img, text="")
        except: pass

    def update_voice_list(self):
        self.cb['values'] = list(self.app.voice_lib.keys())

    def start(self):
        self.app.stop_queue_signal = False
        if not self.file_path:
            messagebox.showwarning("提示", "请先选择图片"); return
        if self.is_running: return
        self.is_running = True; self.btn.config(state="disabled")
        threading.Thread(target=self.work, daemon=True).start()

 

    def work(self):
        """阶段一：本地调度与激活。负责拿Key并获取taskId"""
        start_t = time.time()
        def tick():
            if self.is_running:
                m, s = divmod(int(time.time() - start_t), 60)
                self.lbl_tm.config(text=f"{m:02d}:{s:02d}")
                self.app.root.after(1000, tick)
        tick()

        blacklist = []
        max_activate_retries = 3
        
        # --- 核心排队循环 ---
        while self.is_running:
            # 1. 获取资源 (acquire_key 现在内部自带 CV 阻塞排队和停止信号检测)
            res = self.app.res_manager.acquire_key(blacklist)
            
            # 【重要修改】判断 acquire_key 为何返回
            if res is None: 
                # 只有当 self.app.stop_queue_signal 为 True 时才会返回 None
                self.lbl_st.config(text="🛑 已停止排队", foreground="orange")
                break
            
            # 2. 走到这里说明拿到了可用 Key，立刻更新 UI 负载
            try:
                self.lbl_st.config(text=f"📡 激活中({res['label']})...", foreground="blue")
                self.app.update_monitor() # <-- 新增：让主界面负载数字立刻变动
                
                # 3. 尝试提交以获取 taskId
                submit_res = self._submit_to_server(res['key'])
                
                if submit_res.get("code") == 0:
                    task_id = submit_res["data"]["taskId"]
                    # 【关键点】进入不可打断的执行阶段，此函数执行完必须内部 return 或 release_key
                    self._run_remote_polling(task_id, res)
                    break 
                else:
                    # 提交失败处理
                    print(f"❌ 激活失败: {submit_res.get('msg')}")
                    blacklist.append(res['key'])
                    self.app.res_manager.release_key(res['key'])
                    self.app.update_monitor() # <-- 新增：释放后同步负载
                    
                    if len(blacklist) >= max_activate_retries:
                        self.lbl_st.config(text="❌ 多次激活失败", foreground="red")
                        break
                    time.sleep(1) # 短暂等待重试

            except Exception as e:
                print(f"⚠️ 调度异常: {e}")
                if res: 
                    self.app.res_manager.release_key(res['key'])
                    self.app.update_monitor()
                break

        self.is_running = False
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
                    self.lbl_st.config(text="✅ 处理完成", foreground="green")
                    break
                elif code in [804, 813]:
                    status_text = "运行中" if code == 804 else "云端排队"
                    self.lbl_st.config(text=f"⏳ {status_text}...", foreground="#0078d4")
                elif code == 805:
                    # [优化] 增强健壮性的 data 检查
                    reason = data.get("failedReason") if isinstance(data, dict) else "节点计算失败"
                    self.lbl_st.config(text="❌ 生成失败", foreground="red")
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
            self.lbl_st.config(text="❌ 任务中断", foreground="red")
        finally:
            # 无论如何释放资源
            self.app.res_manager.release_key(api_key)
            self.app.update_monitor()
            self.is_running = False # 确保线程状态同步

    def _handle_download(self, video_url):
        """封装下载保存逻辑"""
        self.lbl_st.config(text="📥 正在下载...", foreground="purple")
        target_dir = self.app.save_dir.get()
        if not os.path.exists(target_dir): os.makedirs(target_dir)
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        
        if core_logic.VideoDownloader.download(video_url, target_dir, filename):
            self.lbl_st.config(text="✅ 完成并保存", foreground="green")
        else:
            self.lbl_st.config(text="❌ 保存失败", foreground="red")


# --- 4. 主程序 ---
class VideoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("1.5")
        self.root.geometry("1100x850")

        # --- 1. 数据初始化 ---
        self.all_data = core_logic.DataIO.load_json("config_and_history.json", {})
        self.global_presets = {
            "aspect_ratio": "9:16",  # 默认竖屏
            "quality": "HD",
            "motion": 5
        }
        
        # API 与 系统参数
        self.web_appid = tk.StringVar(value="1973465795936260097")
        #self.web_appid = tk.StringVar(value="2001838441669246977") # 默认固定ID
        self.sys_prompt = tk.StringVar(value=self.all_data.get("sys_prompt", ""))
        
        # 核心：自定义镜头库管理
        self.custom_motions = self.all_data.get("custom_motions", {})
        
        # 路径与资源
        saved_path = self.all_data.get("save_path")
        if not saved_path: 
            saved_path = os.path.join(os.getcwd(), "downloads")
        self.save_dir = tk.StringVar(value=saved_path)

        self.api_pool = self.all_data.get("api_pool", [])
        self.voice_lib = self.all_data.get("voices", {})
        # 传入 self (即当前 VideoApp 实例)，这样 ResourceManager 才能读取到 stop_queue_signal
        self.res_manager = core_logic.ResourceManager(self, self.api_pool)
        #self.res_manager = core_logic.ResourceManager(self.api_pool)
        self.stop_queue_signal = False
        
        self.tasks = []

        # --- 2. 撤销系统初始化 ---
        self.undo_stack = []  # 结构化撤销栈
        self.redo_stack = []  # 重做栈

        # --- 3. UI 初始化 ---
        self.setup_menu()
        self.setup_ui()
        self.load_history()

        # --- 4. 绑定全局快捷键 ---
        self.root.bind("<Control-z>", self.global_undo)
        self.root.bind("<Control-Z>", self.global_undo)
        self.root.bind("<Control-y>", self.global_redo)
        self.root.bind("<Control-Y>", self.global_redo)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    # --- 撤销/重做核心逻辑 ---

    def global_undo(self, event=None):
        """智能撤销：优先处理文字，其次处理卡片结构"""
        focus_w = self.root.focus_get()
        if isinstance(focus_w, tk.Text):
            try:
                focus_w.edit_undo()
                return "break"
            except Exception: pass
        self.app_level_undo()
        return "break"

    def global_redo(self, event=None):
        """重做逻辑"""
        focus_w = self.root.focus_get()
        if isinstance(focus_w, tk.Text):
            try:
                focus_w.edit_redo()
                return "break"
            except Exception: pass
        self.app_level_redo()
        return "break"

    def record_structure_change(self):
        """在发生 增、删、清空 前调用，保存当前所有卡片快照"""
        snapshot = []
        for t in self.tasks:
            try:
                # 必须确保组件还活着才能读取数据
                if t.frame.winfo_exists():
                    snapshot.append({
                        "img_path": t.file_path,
                        "prompt": t.txt_p.get("1.0", tk.END).strip(),
                        "script": t.txt_s.get("1.0", tk.END).strip(),
                        "char": t.cb.get(),
                        # 【修正】键名统一为 _text，确保被 TaskCard 正确识别
                        "ratio_text": t.cb_ratio.get(),
                        "duration_text": t.cb_dur.get(),
                        "motion_key": t.cb_motion.get()
                    })
            except Exception as e:
                print(f"⚠️ 快照跳过损坏卡片: {e}")
                continue
        
        self.undo_stack.append(snapshot)
        # 限制栈深度
        if len(self.undo_stack) > 30: 
            self.undo_stack.pop(0)
        # 结构改变后，重做栈必须清空，否则会导致状态冲突
        self.redo_stack.clear()

    def app_level_undo(self):
        if not self.undo_stack: return
        
        # 保存当前状态到 redo 栈
        self.redo_stack.append(self._get_current_snapshot())
        
        # 恢复状态
        last_state = self.undo_stack.pop()
        self._apply_snapshot(last_state)

    def app_level_redo(self):
        if not self.redo_stack: return
        
        # 保存当前状态到 undo 栈
        self.undo_stack.append(self._get_current_snapshot())
        
        # 恢复状态
        next_state = self.redo_stack.pop()
        self._apply_snapshot(next_state)

    def _get_current_snapshot(self):
        """内部工具：获取当前 UI 状态快照"""
        snapshot = []
        for t in self.tasks:
            snapshot.append({
                "img_path": t.file_path,
                "prompt": t.txt_p.get("1.0", tk.END).strip(),
                "script": t.txt_s.get("1.0", tk.END).strip(),
                "char": t.cb.get(),
                "ratio": t.cb_ratio.get(),
                "duration": t.cb_dur.get(),
                "motion_key": t.cb_motion.get()
            })
        return snapshot

    def _apply_snapshot(self, state_data):
        """物理重建 UI 卡片"""
        for t in list(self.tasks):
            if t.frame.winfo_exists():
                t.frame.destroy()
        self.tasks.clear()

        for data in state_data:
            # 假设 add_task_card 内部会读取 data["motion_key"]
            self.add_task_card(data, is_undo_op=True)
        
        self.update_monitor()
        self.auto_save_all()

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

    def add_task_card(self, data=None, is_undo_op=False):
        """新建或根据数据恢复卡片"""
        
        # 1. 如果 data 为 None，说明是点击“➕ 新建镜头”按钮触发的
        if data is None and not is_undo_op:
            # 记录撤销状态（你原有的逻辑）
            self.record_structure_change()
            
            # 【关键修改】：从主界面下拉框抓取当前的预设值
            # 这样新建出来的卡片就会直接应用你选好的比例和时长
            data = {
                "ratio_text": self.preset_ratio.get(),
                "duration_text": self.preset_dur.get(),
                "status": "waiting",
                "prompt": "",
                "img_path": ""
            }

        # 2. 创建卡片（此时 data 已经有值了，TaskCard 会读取这些预设）
        card = TaskCard(self.sf, self, data=data)
        self.tasks.append(card)
        
        # 3. UI 刷新逻辑
        self.sf.update_idletasks()
        self.cv.config(scrollregion=self.cv.bbox("all"))
        
        # 4. 只有真正的新建（非加载历史，非撤销）才滚动到底部并保存
        # 这里用一个小技巧判断：如果 data 里的 prompt 是空的，通常代表是刚点的按钮
        if not is_undo_op and data.get("prompt") == "":
            self.cv.yview_moveto(1.0)
            self.auto_save_all()
            
        return card
    

    def clear_all_tasks(self):
        from tkinter import messagebox
        if not self.tasks: return

        msg = ("请选择要删除的范围：\n\n"
               "【是】：删除所有已停止的任务\n"
               "【否】：仅删除未请求（就绪）的任务\n"
               "【取消】：放弃\n\n"
               "提示：撤销快捷键 Ctrl+Z 可找回删除。")
        
        choice = messagebox.askyesnocancel("批量删除", msg)
        if choice is None: return

        # 1. 记录撤销点
        self.record_structure_change()

        # 2. 预筛选：先判断，不销毁
        to_delete = []
        for task in self.tasks:
            try:
                # 运行中的任务绝对不删
                if task.is_running:
                    continue
                
                # 获取状态文本
                status_text = task.lbl_st.cget("text")
                
                # 根据用户选择逻辑进行筛选
                if choice is True:
                    # “是”：只要没在运行，全部加入待删列表
                    to_delete.append(task)
                elif choice is False:
                    # “否”：只有状态为“就绪”的才加入待删列表
                    if status_text == "就绪":
                        to_delete.append(task)
            except Exception:
                # 如果任务已经处于半毁坏状态，保险起见跳过
                continue

        # 3. 统一销毁：此时不再读取任何 UI 属性
        for task in to_delete:
            # 这里的 delete_card_clean 应该包含：
            # 1. task.frame.destroy() 
            # 2. 从 self.tasks 列表中移除自己
            task.delete_card_clean()

        # 4. 刷新界面
        self.sf.update_idletasks()
        self.cv.config(scrollregion=self.cv.bbox("all"))
        self.update_monitor()
        self.auto_save_all()

    def on_closing(self):
        self.auto_save_all()
        self.root.destroy()

    def auto_save_all(self):
        try:
            history = []
            for t in self.tasks:
                if t.frame.winfo_exists():
                    history.append({
                        "img_path": t.file_path,
                        "prompt": t.txt_p.get("1.0", tk.END).strip(),
                        "script": t.txt_s.get("1.0", tk.END).strip(),
                        "char": t.cb.get(),
                        "ratio": t.cb_ratio.get(),
                        "duration": t.cb_dur.get()
                    })
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
        for h in self.all_data.get("task_history", []): 
            self.add_task_card(h, is_undo_op=True) # 载入历史不需要进 undo 栈
        if not self.tasks: self.add_task_card()
        history = self.all_data.get("history", [])
        for data in history:
            self.add_task_card(data)

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