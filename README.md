# How to generate .exe

## 生成32位的程序

1. 打开 Anaconda Prompt​​，以管理员身份运行，避免权限问题。

​​2. 切换至 32 位模式​​

```bash
set CONDA_FORCE_32BIT=1  # 强制后续操作使用 32 位架构[1,2,3,5](@ref)
```

3. ​​创建新环境​​

```bash
conda create -n py32 python=3.8  # 建议选 Python 3.8/3.9（兼容性更好）[2](@ref)
```

py32：自定义环境名称
python=3.8：指定版本（避免选 3.11+，官方库可能缺 32 位包）

4. ​​激活环境并验证​​

```bash
conda activate py32
python -c "import platform; print(platform.architecture())"
```

输出应为：('32bit', 'WindowsPE')


5. 使用 pyinstaller 将 .py 打包成 .exe

```bash
pyinstaller --clean --target-architecture=32bit --add-data ".;." --onefile --noconsole main.py
```
