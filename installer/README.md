# installer

- `Launcher.cs`：查找 pythonw 并以应用目录为工作目录启动 `python -m padlink`；
- `Setup.cs`：WinForms 安装器，解压内嵌 `payload.zip`，创建快捷方式与 HKCU 卸载项；支持 `/S`、`/DIR=`；
- `Uninstall.cs`：反向删除程序、快捷方式与注册表，保留 `%APPDATA%\Win-Pad Connect` 用户数据。

编译请直接运行 `scripts/build-installer.ps1`，不要单独编译 `Setup.cs`（它依赖 `build/payload.zip` 资源）。
