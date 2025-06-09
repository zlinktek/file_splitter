import os
import shutil
import threading
import queue
import binascii
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


class FrameHeaderNotFoundError(Exception):
    """自定义异常：帧头未找到"""

    def __init__(self, position):
        super().__init__(f"在位置 {position} 附近未找到帧头")
        self.position = position


def optimized_split(input_file, output_dir, frame_header, max_size_gb=1, progress_queue=None):
    """
    高性能文件分割方案（支持自定义帧头）
    :param input_file: 输入文件路径
    :param output_dir: 输出目录
    :param frame_header: 自定义帧头（字节序列）
    :param max_size_gb: 单文件最大GB数
    :param progress_queue: 进度队列（用于跨线程通信）
    """
    # 基础参数设置
    HEADER_LEN = len(frame_header)
    max_size = int(max_size_gb * 1024 ** 3)  # 转换为字节

    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)

    # 获取文件大小
    file_size = os.path.getsize(input_file)
    total_processed = 0

    # 存储实际分割位置
    actual_splits = [0]
    current_position = 0

    # 步骤1：动态计算分割点
    with open(input_file, 'rb') as f:
        while current_position + max_size < file_size:
            # 计算下一个分割点（当前+1GB）
            next_target = current_position + max_size

            # 创建向前搜索窗口（确保不超过文件起始位置）
            search_start = max(0, next_target - HEADER_LEN * 100)  # 扩大搜索范围
            search_end = min(file_size, next_target + HEADER_LEN * 2)

            # 定位到搜索区域
            f.seek(search_start)
            search_data = f.read(search_end - search_start)

            # 在窗口内向前搜索帧头
            last_valid_header = None
            pos = 0
            while pos < len(search_data):
                # 查找帧头位置
                header_pos = search_data.find(frame_header, pos)
                if header_pos == -1:
                    break

                # 计算全局位置
                global_pos = search_start + header_pos

                # 只保留在分割点前的帧头位置
                if global_pos <= next_target:
                    last_valid_header = global_pos
                else:
                    # 如果找到的帧头已经超过目标点，停止搜索
                    break

                # 移动到下一个位置
                pos = header_pos + HEADER_LEN

            # 确保找到有效的帧头位置
            if last_valid_header is not None and last_valid_header > current_position:
                actual_splits.append(last_valid_header)
                current_position = last_valid_header
            else:
                # 未找到有效帧头时，抛出异常
                raise FrameHeaderNotFoundError(next_target)

            # 更新进度
            total_processed = current_position
            if progress_queue:
                progress_queue.put(int(total_processed / file_size * 100))

    actual_splits.append(file_size)  # 添加文件结束点

    # 步骤2：直接拷贝数据块
    part_num = 1
    for i in range(len(actual_splits) - 1):
        start = actual_splits[i]
        end = actual_splits[i + 1]
        file_size_bytes = end - start

        # 检查文件大小是否超过限制
        if file_size_bytes > max_size:
            messagebox.showwarning("警告",
                                   f"文件块 {part_num} 大小超出限制: {file_size_bytes / (1024 ** 2):.2f}MB > {max_size_gb}GB")

        output_path = os.path.join(output_dir, f"part_{part_num}.dat")
        part_num += 1

        # 使用系统级拷贝加速
        with open(input_file, 'rb') as src:
            with open(output_path, 'wb') as dest:
                src.seek(start)
                remaining = end - start
                while remaining > 0:
                    chunk_size = min(remaining, 100 * 1024 ** 2)  # 100MB块
                    dest.write(src.read(chunk_size))
                    remaining -= chunk_size

        # 更新进度
        total_processed = end
        if progress_queue:
            progress_queue.put(int(total_processed / file_size * 100))

    return part_num - 1  # 返回生成文件数


def hex_to_bytes(hex_str):
    """将十六进制字符串转换为字节序列"""
    try:
        # 移除空格并转换为小写
        clean_hex = hex_str.replace(" ", "").lower()
        # 验证是否为有效十六进制
        if not all(c in '0123456789abcdef' for c in clean_hex):
            raise ValueError("包含非十六进制字符")
        # 转换字节序列
        return binascii.unhexlify(clean_hex)
    except Exception as e:
        raise ValueError(f"帧头格式错误: {str(e)}")


def browse_input_file(entry_widget):
    input_file = filedialog.askopenfilename(
        title="选择输入.dat文件",
        filetypes=[("DAT files", "*.dat"), ("All files", "*.*")]
    )
    if input_file:
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, input_file)


def browse_output_dir(entry_widget):
    output_dir = filedialog.askdirectory(title="选择输出目录")
    if output_dir:
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, output_dir)


def start_processing(input_entry, output_entry, header_entry, max_size_entry, progress_var, status_label):
    input_file = input_entry.get()
    output_dir = output_entry.get()
    header_text = header_entry.get()

    try:
        max_size_gb = float(max_size_entry.get())
        if max_size_gb <= 0:
            raise ValueError("文件大小必须大于0")
    except ValueError:
        messagebox.showerror("错误", "请输入有效的文件大小（大于0的数字）")
        return

    # 验证输入
    if not input_file or not output_dir or not header_text:
        messagebox.showerror("错误", "请填写所有必填字段！")
        return

    if not os.path.isfile(input_file):
        messagebox.showerror("错误", f"输入文件不存在: {input_file}")
        return

    try:
        # 转换帧头
        frame_header = hex_to_bytes(header_text)
        status_label.config(text=f"使用帧头: {header_text} ({len(frame_header)}字节)")
    except ValueError as e:
        messagebox.showerror("帧头错误", str(e))
        return

    # 创建进度队列（用于线程间通信）
    progress_queue = queue.Queue()

    # 创建后台线程执行分割任务
    def run_split_task():
        try:
            # 执行分割
            num_files = optimized_split(
                input_file,
                output_dir,
                frame_header,
                max_size_gb,
                progress_queue
            )
            root.after(0, lambda: status_label.config(text=f"处理完成！共生成 {num_files} 个文件。"))
            root.after(0, lambda: messagebox.showinfo("完成", f"文件分割完成！共生成 {num_files} 个文件。"))
        except FrameHeaderNotFoundError as e:
            root.after(0, lambda: status_label.config(text="帧头未找到！"))
            root.after(0, lambda: messagebox.showerror("错误", str(e)))
        except Exception as e:
            root.after(0, lambda: status_label.config(text="处理失败！"))
            root.after(0, lambda: messagebox.showerror("错误", f"处理过程中发生错误: {str(e)}"))
        finally:
            root.after(0, lambda: progress_var.set(0))

    # 启动后台线程
    threading.Thread(target=run_split_task, daemon=True).start()

    # 定期检查进度队列并更新UI
    def update_progress_bar():
        try:
            while not progress_queue.empty():
                progress_value = progress_queue.get_nowait()
                progress_var.set(progress_value)
                status_label.config(text=f"处理中... {progress_value}%")
        except queue.Empty:
            pass
        root.after(100, update_progress_bar)  # 每100毫秒检查一次

    # 初始化进度条和状态
    progress_var.set(0)
    status_label.config(text="处理中... 0%")
    update_progress_bar()


# 创建主窗口
root = tk.Tk()
root.title("高性能文件分割助手 (智联电子数据记录仪专用)")
root.geometry("700x400")

# 使用Frame容器组织界面
main_frame = tk.Frame(root, padx=20, pady=20)
main_frame.pack(fill=tk.BOTH, expand=True)

# 输入文件选择区域
input_frame = tk.Frame(main_frame)
input_frame.pack(fill=tk.X, pady=5)
tk.Label(input_frame, text="输入文件 (.dat):", width=15, anchor="w").pack(side=tk.LEFT)
input_entry = tk.Entry(input_frame, width=40)
input_entry.pack(side=tk.LEFT, padx=5)
tk.Button(input_frame, text="浏览...", command=lambda: browse_input_file(input_entry)).pack(side=tk.LEFT)

# 输出目录选择区域
output_frame = tk.Frame(main_frame)
output_frame.pack(fill=tk.X, pady=5)
tk.Label(output_frame, text="输出目录:", width=15, anchor="w").pack(side=tk.LEFT)
output_entry = tk.Entry(output_frame, width=40)
output_entry.pack(side=tk.LEFT, padx=5)
tk.Button(output_frame, text="浏览...", command=lambda: browse_output_dir(output_entry)).pack(side=tk.LEFT)

# 自定义帧头区域
header_frame = tk.Frame(main_frame)
header_frame.pack(fill=tk.X, pady=10)
tk.Label(header_frame, text="数据帧头:", width=15, anchor="w").pack(side=tk.LEFT)
header_entry = tk.Entry(header_frame, width=40)
header_entry.pack(side=tk.LEFT, padx=5)
header_entry.insert(0, "55 AA")  # 默认帧头
tk.Label(header_frame, text="(十六进制格式，如: 55 AA BB)").pack(side=tk.LEFT)

# 文件大小设置
size_frame = tk.Frame(main_frame)
size_frame.pack(fill=tk.X, pady=10)
tk.Label(size_frame, text="文件大小(GB):", width=15, anchor="w").pack(side=tk.LEFT)
max_size_entry = tk.Entry(size_frame, width=10)
max_size_entry.pack(side=tk.LEFT, padx=5)
max_size_entry.insert(0, "1")  # 默认1GB
tk.Label(size_frame, text="(单个文件的最大大小)").pack(side=tk.LEFT)

# 进度条
progress_frame = tk.Frame(main_frame)
progress_frame.pack(fill=tk.X, pady=15)
progress_var = tk.IntVar()
progress_bar = ttk.Progressbar(progress_frame, variable=progress_var, maximum=100, length=600)
progress_bar.pack()

# 状态标签
status_frame = tk.Frame(main_frame)
status_frame.pack(fill=tk.X, pady=10)
status_label = tk.Label(status_frame, text="准备就绪", font=("Arial", 10))
status_label.pack()

# 按钮区域
button_frame = tk.Frame(main_frame)
button_frame.pack(pady=20)
tk.Button(button_frame, text="开始分割",
          command=lambda: start_processing(
              input_entry, output_entry, header_entry, max_size_entry, progress_var, status_label),
          width=20, height=2, bg="#4CAF50", fg="white").pack()

root.mainloop()