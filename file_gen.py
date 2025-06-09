import struct
import os
import argparse
from tkinter import Tk, filedialog


def generate_frames(output_file, num_frames):
    """
    生成指定数量的数据帧
    :param output_file: 输出文件路径
    :param num_frames: 要生成的帧数量
    """
    with open(output_file, 'wb') as f:
        # 全局计数器（4字节整数）
        counter = 0

        for _ in range(num_frames):
            # 写入帧头 55 AA
            f.write(b'\x55\xAA\xBB\xCC')

            # 写入32个4字节递增整数（134-2=132字节 → 132/4=33个整数）
            for _ in range(33):
                # 小端序格式打包4字节整数
                f.write(struct.pack('<I', counter))
                counter += 1  # 计数器递增


def browse_directory(entry_widget):
    """打开目录选择对话框"""
    selected_dir = filedialog.askdirectory(title="选择输出目录")
    if selected_dir:
        entry_widget.delete(0, 'end')
        entry_widget.insert(0, selected_dir)


def main():
    root = Tk()
    root.withdraw()  # 隐藏主窗口

    # 创建文件选择对话框
    output_file = filedialog.asksaveasfilename(
        title="保存数据文件",
        filetypes=[("DAT files", "*.dat"), ("All files", "*.*")],
        defaultextension=".dat"
    )

    if not output_file:
        print("操作已取消")
        return

    # 获取用户输入
    num_frames = int(input("请输入要生成的帧数量: "))

    print(f"开始生成 {num_frames} 帧数据...")
    generate_frames(output_file, num_frames)

    file_size = os.path.getsize(output_file)
    print(f"文件已生成: {output_file}")
    print(f"文件大小: {file_size / (1024 * 1024):.2f} MB")
    print(f"总帧数: {num_frames} | 每帧大小: 134 字节")


if __name__ == "__main__":
    main()